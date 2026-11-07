"""T101: rollback restores the previous version without deleting data."""

import pytest
import seed_fixtures as sf
from conftest import KNOWN
from db.tables import outbox, seed_datasets, seed_rows
from seeds.lifecycle import LifecycleError, activate, active_dataset, register_upload, rollback, validate_dataset
from sqlalchemy import func, select
from upload_settings import ParseLimits

L = ParseLimits()


def make(conn, store, data):
    up = register_upload(conn, store, "datos.csv", data, "x", "buyer-1", L)
    validate_dataset(conn, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-1", L)
    return up["id"]


def two_versions(conn, store):
    a = make(conn, store, sf.static("valid.csv"))
    activate(conn, store, a, "buyer-1")
    b = make(conn, store, sf.static("valid.csv").replace(b"2026-01-05", b"2026-01-06"))
    activate(conn, store, b, "buyer-1")
    return a, b


def test_rollback_restores_the_previous_version_and_keeps_every_row(conn, store):
    a, b = two_versions(conn, store)
    rows_before = conn.execute(select(func.count()).select_from(seed_rows)).scalar()
    out = rollback(conn, store, "admin-1")
    assert out == {"id": b, "status": "rolled_back", "restored": a} and active_dataset(conn).id == a
    assert conn.execute(select(func.count()).select_from(seed_rows)).scalar() == rows_before
    assert {r.id: r.status for r in conn.execute(select(seed_datasets)).all()} == {a: "active", b: "rolled_back"}
    assert [e.type for e in conn.execute(select(outbox)).all()].count("forecast.seed.activated.v1") == 3         # two activations and the rollback each request a run


def test_rolling_back_the_only_dataset_leaves_none_active(conn, store):
    a = make(conn, store, sf.static("valid.csv"))
    activate(conn, store, a, "buyer-1")
    assert rollback(conn, store, "buyer-1")["restored"] is None and active_dataset(conn) is None


def test_nothing_to_roll_back_is_refused(conn, store):
    with pytest.raises(LifecycleError) as e:
        rollback(conn, store, "buyer-1")
    assert e.value.code == "import_dataset_state"
