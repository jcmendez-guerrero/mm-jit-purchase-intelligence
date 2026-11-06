"""T152: every service's migrations run on a real PostgreSQL, match the code's table definitions, and are reversible.

Needs Docker. Skipped unless RUN_PG_MIGRATIONS=1 (CI sets it). It starts its own throwaway PostgreSQL from the same
digest-pinned image and init script as the Compose stack, so it never touches a running stack.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
SERVICES = {  # service -> (schema, role)
    "siweb-connector": ("integration", "integration_svc"),
    "inventory-service": ("inventory", "inventory_svc"),
    "forecast-service": ("forecasting", "forecasting_svc"),
    "procurement-service": ("procurement", "procurement_svc"),
    "siweb-cost-writer": ("costwrite", "costwrite_svc"),
    "api-bff": ("bff", "bff_svc"),
}
EXTERNAL_PORT = os.environ.get("MMI_PG_EXTERNAL_PORT")   # an already running PostgreSQL with infra/postgres/init.sql applied (no Docker needed)
pytestmark = pytest.mark.skipif(not (os.environ.get("RUN_PG_MIGRATIONS") and (EXTERNAL_PORT or shutil.which("docker"))),
                                reason="needs RUN_PG_MIGRATIONS=1 and Docker (or MMI_PG_EXTERNAL_PORT)")


def image() -> str:
    m = re.search(r"image:\s*(postgres:16@sha256:[0-9a-f]{64})", (ROOT / "infra/compose.yaml").read_text())
    assert m, "compose must pin the postgres image by digest"
    return m.group(1)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def pg_port():
    if EXTERNAL_PORT:
        yield int(EXTERNAL_PORT)
        return
    port, name = free_port(), f"mmi-migrations-{os.getpid()}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-e", "POSTGRES_DB=mmi", "-e", "POSTGRES_USER=mmi_admin", "-e", "POSTGRES_PASSWORD=dev-only-local",
                    "-p", f"127.0.0.1:{port}:5432", "-v", f"{ROOT / 'infra/postgres/init.sql'}:/docker-entrypoint-initdb.d/00-init.sql:ro", image()],
                   check=True, capture_output=True)
    try:
        stable = 0
        for _ in range(90):                      # the image restarts the server after running the init script: wait for it to stay up
            try:
                import psycopg

                with psycopg.connect(f"host=127.0.0.1 port={port} dbname=mmi user=mmi_admin password=dev-only-local", connect_timeout=2) as c:
                    n = c.execute("select count(*) from pg_namespace where nspname in ('integration','inventory','forecasting','procurement','costwrite','bff')").fetchone()
                stable = stable + 1 if n and n[0] == 6 else 0
            except Exception:
                stable = 0
            if stable >= 3:
                break
            time.sleep(1)
        else:
            pytest.fail("PostgreSQL did not become ready")
        yield port
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def url(role: str, port: int) -> str:
    return f"postgresql+psycopg://{role}:dev-only-local@127.0.0.1:{port}/mmi"


def alembic(service: str, role: str, port: int, *args: str) -> None:
    r = subprocess.run([str(Path(PY).parent / "alembic"), *args], cwd=ROOT / "services" / service, env={**os.environ, "MMI_DATABASE_URL": url(role, port)},
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]


def declared(service: str) -> dict[str, dict[str, bool]]:
    """table -> {column: nullable}, read from the service's own SQLAlchemy metadata in a clean interpreter."""
    code = ("import json,sys; sys.path.insert(0,'src'); from db.tables import metadata; "
            "print(json.dumps({t.name:{c.name:bool(c.nullable) and not c.primary_key for c in t.columns} for t in metadata.tables.values()}))")
    r = subprocess.run([PY, "-c", code], cwd=ROOT / "services" / service, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(ROOT / "packages/contracts/python")})
    assert r.returncode == 0, r.stderr[-1500:]
    return json.loads(r.stdout.strip().splitlines()[-1])  # type: ignore[no-any-return]


def actual(port: int, schema: str, role: str) -> dict[str, dict[str, bool]]:
    import sqlalchemy as sa

    eng = sa.create_engine(url(role, port))
    out: dict[str, dict[str, bool]] = {}
    with eng.connect() as c:
        for t, col, nullable in c.execute(sa.text("select table_name, column_name, is_nullable from information_schema.columns where table_schema = :s"), {"s": schema}):
            if t != "alembic_version":
                out.setdefault(t, {})[col] = nullable == "YES"
    return out


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_migrations_match_the_code_and_are_reversible(service, pg_port):
    schema, role = SERVICES[service]
    alembic(service, role, pg_port, "upgrade", "head")
    want, got = declared(service), actual(pg_port, schema, role)
    assert set(got) == set(want), f"tables differ: only in code {sorted(set(want) - set(got))}, only in database {sorted(set(got) - set(want))}"
    for table, cols in want.items():
        assert set(got[table]) == set(cols), f"{table}: columns differ"
        for col, nullable in cols.items():
            assert got[table][col] == nullable or (nullable is False and got[table][col] is True), f"{table}.{col}: nullability differs"
    alembic(service, role, pg_port, "downgrade", "base")
    assert actual(pg_port, schema, role) == {}, "downgrade left tables behind"
    alembic(service, role, pg_port, "upgrade", "head")


def test_a_service_role_cannot_touch_another_services_schema(pg_port):
    import sqlalchemy as sa

    with sa.create_engine(url("inventory_svc", pg_port)).connect() as c:
        with pytest.raises(sa.exc.ProgrammingError):
            c.execute(sa.text("select 1 from procurement.audit_events"))


def sql(port: int, role: str, statement: str, params: dict | None = None):  # type: ignore[type-arg]
    import sqlalchemy as sa

    with sa.create_engine(url(role, port)).begin() as c:
        return c.execute(sa.text(statement), params or {})


def _seed_cost(port: int) -> str:
    import uuid

    sid, cid = str(uuid.uuid4()), str(uuid.uuid4())
    sql(port, "procurement_svc", "insert into suppliers (id, external_contact_id, name) values (:i, :c, 'P')", {"i": sid, "c": int(uuid.uuid4().int % 10**8)})
    sql(port, "procurement_svc", "insert into supplier_costs (id, product_id, supplier_id, version, cost_with_recargo, entered_includes_recargo, source, verified_at, "
        "created_at, created_by) values (:i, 1, :s, 1, 10, true, 'manual', now(), now(), 'x')", {"i": cid, "s": sid})
    return cid


def test_audit_trails_and_cost_versions_cannot_be_rewritten_through_sql(pg_port):
    import sqlalchemy as sa

    alembic("procurement-service", "procurement_svc", pg_port, "upgrade", "head")
    alembic("siweb-cost-writer", "costwrite_svc", pg_port, "upgrade", "head")
    sql(pg_port, "procurement_svc", "insert into audit_events (ts, actor, action, entity, entity_id, prev_hash, hash) values (now(), 'a', 'x', 'e', '1', :p, :h)",
        {"p": "0" * 64, "h": "1" * 64})
    for stmt in ("update audit_events set actor = 'evil'", "delete from audit_events", "truncate audit_events", "truncate supplier_costs"):
        with pytest.raises(sa.exc.DBAPIError, match=r"append-only|immutable|never deleted"):
            sql(pg_port, "procurement_svc", stmt)
    cid = _seed_cost(pg_port)
    with pytest.raises(sa.exc.DBAPIError, match="immutable"):
        sql(pg_port, "procurement_svc", "update supplier_costs set cost_with_recargo = 1 where id = :i", {"i": cid})
    with pytest.raises(sa.exc.DBAPIError, match="never deleted"):
        sql(pg_port, "procurement_svc", "delete from supplier_costs where id = :i", {"i": cid})
    # the attestations the application legitimately changes still work
    sql(pg_port, "procurement_svc", "update supplier_costs set verified_at = now(), verified_by = 'buyer', jump_confirmed_by = 'buyer', jump_confirmed_at = now(), "
        "superseded_by = 'next' where id = :i", {"i": cid})
    with pytest.raises(sa.exc.DBAPIError, match="re-pointed"):
        sql(pg_port, "procurement_svc", "update supplier_costs set superseded_by = 'other' where id = :i", {"i": cid})
    sql(pg_port, "costwrite_svc", "insert into writer_audit (ts, request_id, actor_ref, action, prev_hash, hash) values (now(), 'r', 'a', 'x', :p, :h)", {"p": "0" * 64, "h": "1" * 64})
    sql(pg_port, "costwrite_svc", "insert into write_attempts (request_id, attempt, started_at, outcome) values ('r', 1, now(), 'sent')")
    for stmt in ("update writer_audit set actor_ref = 'evil'", "delete from writer_audit", "update write_attempts set outcome = 'succeeded'", "delete from write_attempts",
                 "truncate writer_audit", "truncate write_attempts"):
        with pytest.raises(sa.exc.DBAPIError, match="append-only"):
            sql(pg_port, "costwrite_svc", stmt)


def test_mmi002_append_only_tables_and_constraints(pg_port):
    """T021: the lot-cost ledger and the new audit tables cannot be rewritten through SQL; one seed dataset can be active."""
    import uuid

    import sqlalchemy as sa

    alembic("procurement-service", "procurement_svc", pg_port, "upgrade", "head")
    alembic("forecast-service", "forecasting_svc", pg_port, "upgrade", "head")
    alembic("inventory-service", "inventory_svc", pg_port, "upgrade", "head")
    alembic("api-bff", "bff_svc", pg_port, "upgrade", "head")

    sid, lid = str(uuid.uuid4()), str(uuid.uuid4())
    sql(pg_port, "procurement_svc", "insert into suppliers (id, external_contact_id, name) values (:i, :c, 'P')", {"i": sid, "c": int(uuid.uuid4().int % 10**8)})
    sql(pg_port, "procurement_svc", "insert into lot_acquisition_costs (id, variant_id, supplier_id, lot, quantity, unit_cost, source, recorded_by, recorded_at) "
        "values (:i, 9001, :s, 'L-01', 6, 10.5, 'confirmed_order', 'buyer', now())", {"i": lid, "s": sid})
    for stmt in ("update lot_acquisition_costs set unit_cost = 1", "delete from lot_acquisition_costs", "truncate lot_acquisition_costs"):
        with pytest.raises(sa.exc.DBAPIError, match="append-only"):
            sql(pg_port, "procurement_svc", stmt)

    for role in ("bff_svc", "forecasting_svc", "inventory_svc"):
        sql(pg_port, role, "insert into audit_events (ts, actor, action, entity, entity_id, prev_hash, hash) values (now(), 'a', 'x', 'e', '1', :p, :h)",
            {"p": "0" * 64, "h": "1" * 64})
        for stmt in ("update audit_events set actor = 'evil'", "delete from audit_events", "truncate audit_events"):
            with pytest.raises(sa.exc.DBAPIError, match="append-only"):
                sql(pg_port, role, stmt)

    def dataset(status: str, version: int) -> None:
        sql(pg_port, "forecasting_svc", "insert into seed_datasets (id, version, status, origin, file_sha256, uploader, uploaded_at) values (:i, :v, :s, 'synthetic', :h, 'buyer', now())",
            {"i": str(uuid.uuid4()), "v": version, "s": status, "h": "a" * 64})

    dataset("active", 1)
    dataset("superseded", 2)
    with pytest.raises(sa.exc.IntegrityError):          # a second active dataset is refused by the database
        dataset("active", 3)
