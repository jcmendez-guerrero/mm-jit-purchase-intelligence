"""MMI-7 T020 + T058: two real concurrent activations on PostgreSQL: one wins, the other gets `import_conflict`.

Runs only with RUN_PG_MIGRATIONS=1 and MMI_PG_EXTERNAL_PORT (a PostgreSQL with infra/postgres/init.sql applied, as in infra/tests/test_migrations_postgres.py);
it migrates the forecast schema to head first and removes the rows it created.
"""

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import seed_fixtures as sf
from conftest import KNOWN
from db.tables import import_jobs, seed_datasets, seed_quarantine, seed_rows
from seeds.lifecycle import LifecycleError, activate, active_dataset, register_upload, validate_dataset
from sqlalchemy import create_engine, delete
from upload_settings import ParseLimits

PORT = os.environ.get("MMI_PG_EXTERNAL_PORT")
pytestmark = pytest.mark.skipif(not (os.environ.get("RUN_PG_MIGRATIONS") and PORT), reason="needs RUN_PG_MIGRATIONS=1 and MMI_PG_EXTERNAL_PORT")

L = ParseLimits()
SKUS = {f"EJ-{v}": v for v in KNOWN}
URL = f"postgresql+psycopg://forecasting_svc:dev-only-local@127.0.0.1:{PORT}/mmi"
SERVICE = Path(__file__).resolve().parents[1]


@pytest.fixture
def pg_engine():
    r = subprocess.run([str(Path(sys.executable).parent / "alembic"), "upgrade", "head"], cwd=SERVICE, env={**os.environ, "MMI_DATABASE_URL": URL}, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]
    engine = create_engine(URL)
    yield engine
    engine.dispose()


def validated(engine, store, data):
    with engine.begin() as c:
        up = register_upload(c, store, "datos.csv", data, "Hoja", "buyer-1", L)
        validate_dataset(c, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-2", L, sku_map=SKUS)
    return up["id"]


def test_two_concurrent_activations_one_wins_and_the_other_is_told_it_conflicted(pg_engine, store):
    a = validated(pg_engine, store, sf.static("valid.csv").replace(b"2026-01-05", b"2026-02-05"))
    b = validated(pg_engine, store, sf.static("valid.csv").replace(b"2026-01-05", b"2026-02-06"))
    result: dict[str, object] = {}
    try:
        first = pg_engine.connect()
        tx = first.begin()
        assert activate(first, store, a, "approver-1")["status"] == "active"                  # not committed yet: it holds the single active slot

        def second() -> None:
            with pg_engine.connect() as c2:
                t2 = c2.begin()
                try:
                    result["out"] = activate(c2, store, b, "approver-2")
                    t2.commit()
                except LifecycleError as exc:
                    result["code"] = exc.code
                    t2.rollback()

        worker = threading.Thread(target=second)
        worker.start()
        time.sleep(1.5)
        assert worker.is_alive(), "the second activation should wait for the first transaction"
        tx.commit()
        first.close()
        worker.join(timeout=20)
        assert not worker.is_alive()
        assert result == {"code": "import_conflict"}
        with pg_engine.connect() as c:
            assert active_dataset(c).id == a
    finally:
        with pg_engine.begin() as c:
            c.execute(delete(import_jobs).where(import_jobs.c.dataset_id.in_([a, b])))
            c.execute(delete(seed_rows).where(seed_rows.c.dataset_id.in_([a, b])))
            c.execute(delete(seed_quarantine).where(seed_quarantine.c.dataset_id.in_([a, b])))
            c.execute(delete(seed_datasets).where(seed_datasets.c.id.in_([a, b])))



def test_two_concurrent_rollbacks_one_wins_and_the_other_is_told_it_conflicted(pg_engine, store):
    """MMI-7 T074 (FR-019): the second rollback waits for the first one's row lock, then finds the dataset no longer active."""
    from seeds.lifecycle import rollback

    a = validated(pg_engine, store, sf.static("valid.csv").replace(b"2026-01-05", b"2026-02-07"))
    with pg_engine.begin() as c:
        activate(c, store, a, "approver-1")
    result: dict[str, object] = {}
    try:
        first = pg_engine.connect()
        tx = first.begin()
        assert rollback(first, store, "approver-1", reason_code="wrong_figures")["status"] == "rolled_back"          # not committed yet: it holds the row lock

        def second() -> None:
            with pg_engine.connect() as c2:
                t2 = c2.begin()
                try:
                    result["out"] = rollback(c2, store, "approver-2", reason_code="test")
                    t2.commit()
                except LifecycleError as exc:
                    result["code"] = exc.code
                    t2.rollback()

        worker = threading.Thread(target=second)
        worker.start()
        time.sleep(1.5)
        assert worker.is_alive(), "the second rollback should wait for the first transaction"
        tx.commit()
        first.close()
        worker.join(timeout=20)
        assert not worker.is_alive()
        assert result == {"code": "import_conflict"}
        with pg_engine.connect() as c:
            assert active_dataset(c) is None
    finally:
        with pg_engine.begin() as c:
            c.execute(delete(import_jobs).where(import_jobs.c.dataset_id == a))
            c.execute(delete(seed_rows).where(seed_rows.c.dataset_id == a))
            c.execute(delete(seed_quarantine).where(seed_quarantine.c.dataset_id == a))
            c.execute(delete(seed_datasets).where(seed_datasets.c.id == a))
