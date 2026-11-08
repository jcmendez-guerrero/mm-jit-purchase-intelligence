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
    assert {f.state for f in old} == {"stale"}
    assert fresh[0].as_json()["refreshed_at_original"] == fresh[0].refreshed_at.isoformat()


def test_aggregate_rows_keep_working_and_carry_the_new_columns(engine):
    seed_reference(engine)
    with engine.begin() as c:
        refresh_aggregates(c, TODAY, None, NOW)
    with engine.connect() as c:
        row = c.execute(select(agg_daily_kpis).limit(1)).first()
    assert row.origin == "erp_sync" and row.capital_tied_up is None and row.demand_units is None and row.forecast_units is None


def test_migration_0007_chains_after_0006_and_adds_the_four_columns():
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0007_dashboard_columns.py"
    spec = importlib.util.spec_from_file_location("m0007", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert (mod.revision, mod.down_revision) == ("0007", "0006")
    source = path.read_text(encoding="utf-8")
    for col in ("capital_tied_up", "demand_units", "forecast_units", "origin"):
        assert source.count(f'"{col}"') >= 2          # added in upgrade, dropped in downgrade
