"""T009 (forecast): migration 0006 adds the explanation and per-product backtest tables and reverses cleanly."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

NEW_TABLES = {"forecast_explanations", "product_backtest"}


def _load():
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0006_explanations_backtest.py"
    spec = importlib.util.spec_from_file_location("m0006", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(conn, fn):
    with Operations.context(MigrationContext.configure(conn)):
        fn()


def test_revision_chain_points_at_0005():
    mod = _load()
    assert (mod.revision, mod.down_revision) == ("0006", "0005")


def test_upgrade_then_downgrade_round_trip_leaves_existing_tables_alone():
    mod = _load()
    eng = sa.create_engine("sqlite://")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE forecast_runs (id VARCHAR(36) PRIMARY KEY)")
        conn.exec_driver_sql("INSERT INTO forecast_runs VALUES ('r1')")
        _run(conn, mod.upgrade)
        assert NEW_TABLES <= set(sa.inspect(conn).get_table_names())
        _run(conn, mod.downgrade)
        assert not NEW_TABLES & set(sa.inspect(conn).get_table_names())
        assert conn.exec_driver_sql("SELECT id FROM forecast_runs").scalar() == "r1"


def test_one_backtest_row_per_run_and_variant():
    from db.tables import metadata, product_backtest
    from sqlalchemy import insert
    from sqlalchemy.exc import IntegrityError

    eng = sa.create_engine("sqlite://")
    metadata.create_all(eng)
    row = {"backtest_run_id": "b1", "variant_id": 7, "periods": 4, "beats_baseline": True, "model_version": "m1", "created_at": sa.func.now()}
    with eng.begin() as conn:
        conn.execute(insert(product_backtest).values(**row))
    try:
        with eng.begin() as conn:
            conn.execute(insert(product_backtest).values(**row))
        raise AssertionError("duplicate backtest row accepted")
    except IntegrityError:
        pass
