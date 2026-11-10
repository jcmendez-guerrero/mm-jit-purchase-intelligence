"""T011 and T007: freshness states, the stale threshold, and the extended aggregate table."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dashboard.freshness import classify, inventory_freshness, stale_after_hours
from dashboard.kpis import refresh_aggregates
from db.tables import agg_daily_kpis
from reference_dataset import NOW, TODAY, seed_reference
from sqlalchemy import select

NOW_DT = datetime(2026, 11, 9, 12, tzinfo=UTC)


def test_state_is_no_data_ok_or_stale_by_the_threshold():
    assert classify(None, NOW_DT, 48) == "no_data"
    assert classify(NOW_DT - timedelta(hours=47), NOW_DT, 48) == "ok"
    assert classify(NOW_DT - timedelta(hours=49), NOW_DT, 48) == "stale"
    assert classify(datetime(2026, 11, 9, 11), NOW_DT, 48) == "ok"  # noqa: DTZ001 - a naive value is read as UTC on purpose


def test_the_threshold_comes_from_the_server_with_a_safe_default(monkeypatch):
    monkeypatch.delenv("DASHBOARD_STALE_AFTER_HOURS", raising=False)
    assert stale_after_hours() == 48
    monkeypatch.setenv("DASHBOARD_STALE_AFTER_HOURS", "24")
    assert stale_after_hours() == 24
    monkeypatch.setenv("DASHBOARD_STALE_AFTER_HOURS", "-5")
    assert stale_after_hours() == 48


def test_an_empty_database_reports_no_data_for_every_source(engine):
    with engine.connect() as c:
        out = inventory_freshness(c, NOW_DT)
    assert out and all(f.state == "no_data" and f.refreshed_at is None for f in out)


def test_loaded_data_reports_ok_then_stale_with_origin(engine):
    seed_reference(engine)
    with engine.begin() as c:
        refresh_aggregates(c, TODAY, None, NOW)
    with engine.connect() as c:
        fresh = inventory_freshness(c, NOW_DT)
        old = inventory_freshness(c, NOW_DT + timedelta(days=5))
    assert {f.state for f in fresh} == {"ok"} and {f.origin for f in fresh} == {"erp_sync"}
    assert [f.source for f in fresh] == ["inventory_snapshot", "movements", "aggregates"]        # one entry per source name
    assert {f.state for f in old} == {"stale"}
    assert fresh[0].refreshed_at.hour == 8 and fresh[0].original is None             # the real collection time, not midnight; this source keeps no original text


def test_aggregate_rows_keep_working_and_carry_the_new_columns(engine):
    seed_reference(engine)
    with engine.begin() as c:
        refresh_aggregates(c, TODAY, None, NOW)
    with engine.connect() as c:
        row = c.execute(select(agg_daily_kpis).limit(1)).first()
    assert row.origin == "erp_sync" and row.capital_tied_up is None and row.demand_units is None and row.forecast_units is None


def test_migration_0007_upgrades_and_downgrades_a_real_table():
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0007_dashboard_columns.py"
    spec = importlib.util.spec_from_file_location("m0007", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert (mod.revision, mod.down_revision) == ("0007", "0006")
    new = {"capital_tied_up", "demand_units", "forecast_units", "origin"}
    eng = sa.create_engine("sqlite://")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE agg_daily_kpis (id INTEGER PRIMARY KEY, day DATE NOT NULL, inventory_value NUMERIC NOT NULL)")
        conn.exec_driver_sql("INSERT INTO agg_daily_kpis (day, inventory_value) VALUES ('2026-11-09', 5)")
        with Operations.context(MigrationContext.configure(conn)):
            mod.upgrade()
        assert new <= {c["name"] for c in sa.inspect(conn).get_columns("agg_daily_kpis")}
        assert conn.exec_driver_sql("SELECT origin FROM agg_daily_kpis").scalar() == "erp_sync"      # old rows get the default
        with Operations.context(MigrationContext.configure(conn)):
            mod.downgrade()
        assert not new & {c["name"] for c in sa.inspect(conn).get_columns("agg_daily_kpis")}
        assert conn.exec_driver_sql("SELECT inventory_value FROM agg_daily_kpis").scalar() == 5       # data survives the round trip


def test_movements_report_the_utc_time_and_the_original_string(engine):
    from db.tables import stock_movements
    from sqlalchemy import insert

    seed_reference(engine)
    with engine.begin() as c:
        c.execute(insert(stock_movements).values(external_id=1, created_at_utc=datetime(2026, 11, 9, 6, 30, tzinfo=UTC), created_at_raw="2026-11-09T07:30:00+01:00",
                                                 variant_id=1, warehouse_id=1, quantity=-1, reason="sale"))
    with engine.connect() as c:
        moves = next(f for f in inventory_freshness(c, NOW_DT) if f.source == "movements")
    assert moves.refreshed_at.hour == 6 and moves.state == "ok"
    assert moves.as_json()["refreshed_at_original"] == "2026-11-09T07:30:00+01:00"
