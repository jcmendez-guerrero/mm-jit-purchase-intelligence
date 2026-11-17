"""Feature 014 (T016, 006 T078, edge case "daylight-saving change"): the dashboard's day is the Madrid business day, also on the two clock-change days of 2026.

Spain moves its clocks on 2026-03-29 (a 23-hour day) and 2026-10-25 (a 25-hour day). Demand rows are keyed by the Madrid business day, so "today" must be the Madrid date,
not the UTC date, or the first hours of a Madrid day would be read as the day before.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from dashboard.filters import FilterSet
from dashboard.kpis import Filters, _on_hand, business_today, demand_summary, demand_trend
from db.tables import demand_observations, products, stock_snapshots, variants
from sqlalchemy import insert

SPRING = date(2026, 3, 29)
AUTUMN = date(2026, 10, 25)


@pytest.mark.parametrize(
    ("utc", "madrid_day"),
    [
        (datetime(2026, 3, 28, 22, 30, tzinfo=UTC), date(2026, 3, 28)),      # 23:30 CET the evening before the change
        (datetime(2026, 3, 28, 23, 30, tzinfo=UTC), SPRING),                 # 00:30 CET: already the 29th although UTC says the 28th
        (datetime(2026, 3, 29, 1, 30, tzinfo=UTC), SPRING),                  # 03:30 CEST, after the clocks jumped
        (datetime(2026, 3, 29, 22, 30, tzinfo=UTC), date(2026, 3, 30)),      # 00:30 CEST on the 30th
        (datetime(2026, 10, 24, 22, 30, tzinfo=UTC), AUTUMN),                # 00:30 CEST on the 25th
        (datetime(2026, 10, 25, 22, 30, tzinfo=UTC), AUTUMN),                # 23:30 CET: the 25th lasts 25 hours
        (datetime(2026, 10, 25, 23, 30, tzinfo=UTC), date(2026, 10, 26)),    # 00:30 CET on the 26th
    ],
)
def test_the_business_day_is_the_madrid_date_around_each_clock_change(utc, madrid_day):
    assert business_today(utc) == madrid_day


def _seed(engine, days):
    with engine.begin() as c:
        c.execute(insert(products).values(external_id=1, name="Sintético", status="active", missed_syncs=0, clinical_critical=False))
        c.execute(insert(variants).values(external_id=1, product_id=1, sku="SYN-001", name="Sintético", pack_size=1, uom="u", reorder_point=1, price=1))
        c.execute(insert(demand_observations).values([{"variant_id": 1, "warehouse_id": 1, "day": d, "demand_qty": 2, "censored": False, "lineage": "m"} for d in days]))


@pytest.mark.parametrize("change_day", [SPRING, AUTUMN])
def test_the_trend_has_one_whole_bucket_for_the_change_day_and_none_missing_or_doubled(engine, change_day):
    week = [change_day + timedelta(days=i) for i in range(-3, 4)]        # three days either side
    _seed(engine, week)
    end = change_day + timedelta(days=3)
    with engine.connect() as c:
        trend = demand_trend(c, end, 7, Filters())
        total = demand_summary(c, end, 7, Filters())
    assert [p["day"] for p in trend] == [d.isoformat() for d in sorted(week)]
    assert [p["actual"] for p in trend] == [2] * 7 and total["units"] == 14


@pytest.mark.parametrize("change_day", [SPRING, AUTUMN])
def test_the_period_filter_accepts_a_range_that_ends_on_the_change_day(change_day):
    fs = FilterSet.parse(change_day, change_day - timedelta(days=6), None)
    assert (fs.date_from, fs.date_to) == (change_day - timedelta(days=6), change_day) and fs.clipped_to_today is False
    clipped = FilterSet.parse(change_day, None, change_day + timedelta(days=1))
    assert clipped.date_to == change_day and clipped.clipped_to_today is True


@pytest.mark.parametrize("change_day", [SPRING, AUTUMN])
def test_the_stock_snapshot_of_the_change_day_is_the_one_used_that_day_and_not_the_day_before(engine, change_day):
    _seed(engine, [change_day])
    with engine.begin() as c:
        c.execute(insert(stock_snapshots).values([
            {"variant_id": 1, "warehouse_id": 1, "snapshot_date": change_day - timedelta(days=1), "on_hand": 3, "available": 3, "reserved": 0},
            {"variant_id": 1, "warehouse_id": 1, "snapshot_date": change_day, "on_hand": 5, "available": 5, "reserved": 0}]))
    with engine.connect() as c:
        assert _on_hand(c, change_day, 1) == {1: 5} and _on_hand(c, change_day - timedelta(days=1), 1) == {1: 3}


def test_the_risk_evaluation_and_the_variant_history_default_to_the_madrid_day_not_the_utc_day(engine, monkeypatch):
    """T081 (feature 014): outside the dashboard routes the default "today" is the Madrid business day too (FR-022)."""
    from reference_dataset import seed_reference
    from risk.daily import evaluate_risks

    seed_reference(engine)
    monkeypatch.setattr("risk.daily.business_today", lambda: date(2026, 11, 9))
    with engine.connect() as c:
        assert evaluate_risks(c) == evaluate_risks(c, as_of=date(2026, 11, 9))            # no as_of: the Madrid day, the one the helper returns


def test_every_default_today_in_the_inventory_service_comes_from_the_one_helper():
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    offenders = [str(p.relative_to(src)) for p in src.rglob("*.py") if "datetime.now(UTC).date()" in p.read_text(encoding="utf-8")]
    assert offenders == []
