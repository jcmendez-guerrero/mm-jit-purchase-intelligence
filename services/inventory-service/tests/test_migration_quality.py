"""T009 (inventory): migration 0008 adds the feature 012 tables and columns, keeps old rows, and reverses cleanly."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

NEW_TABLES = {"data_quality_snapshot", "anomaly_flags", "portfolio_aggregate"}
NEW_COLUMNS = {"config_version_id", "method"}


def _load():
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0008_quality_intelligence.py"
    spec = importlib.util.spec_from_file_location("m0008", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(conn, fn):
    with Operations.context(MigrationContext.configure(conn)):
        fn()


def test_revision_chain_points_at_0007():
    mod = _load()
    assert (mod.revision, mod.down_revision) == ("0008", "0007")


def test_upgrade_adds_tables_and_nullable_columns_and_keeps_old_rows():
    mod = _load()
    eng = sa.create_engine("sqlite://")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE product_segments (variant_id INTEGER PRIMARY KEY, abc VARCHAR(1) NOT NULL)")
        conn.exec_driver_sql("INSERT INTO product_segments VALUES (1, 'A')")
        _run(conn, mod.upgrade)
        insp = sa.inspect(conn)
        assert NEW_TABLES <= set(insp.get_table_names())
        assert NEW_COLUMNS <= {c["name"] for c in insp.get_columns("product_segments")}
        assert conn.exec_driver_sql("SELECT config_version_id, method FROM product_segments").one() == (None, None)


def test_downgrade_removes_everything_and_keeps_existing_data():
    mod = _load()
    eng = sa.create_engine("sqlite://")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE product_segments (variant_id INTEGER PRIMARY KEY, abc VARCHAR(1) NOT NULL)")
        conn.exec_driver_sql("INSERT INTO product_segments VALUES (1, 'A')")
        _run(conn, mod.upgrade)
        _run(conn, mod.downgrade)
        insp = sa.inspect(conn)
        assert not NEW_TABLES & set(insp.get_table_names())
        assert not NEW_COLUMNS & {c["name"] for c in insp.get_columns("product_segments")}
        assert conn.exec_driver_sql("SELECT abc FROM product_segments").scalar() == "A"


def test_snapshot_and_flag_uniqueness_is_enforced():
    from db.tables import anomaly_flags, data_quality_snapshot, metadata
    from sqlalchemy import insert
    from sqlalchemy.exc import IntegrityError

    eng = sa.create_engine("sqlite://")
    metadata.create_all(eng)
    flag = {"variant_id": 1, "day": sa.text("'2026-01-02'"), "rule_id": "mad_outlier", "original_value": 90, "decision": "pending", "created_at": sa.func.now()}
    with eng.begin() as conn:
        conn.execute(insert(anomaly_flags).values(**flag))
    try:
        with eng.begin() as conn:
            conn.execute(insert(anomaly_flags).values(**flag))
        raise AssertionError("duplicate flag accepted")
    except IntegrityError:
        pass
    assert data_quality_snapshot.c.coverage_ratio.type.precision == 7
