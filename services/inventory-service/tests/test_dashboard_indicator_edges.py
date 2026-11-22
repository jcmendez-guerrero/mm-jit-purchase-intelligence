"""Feature 014 (T052, US1/US6, 006 T018): the indicators on awkward data: no demand, negative or zero stock, an estimated cost, incomplete records. Nothing is hidden and nothing is a silent zero.

Synthetic reference dataset (TOTALS.md): five products, one lot without any cost (SYN-003), one cost taken from another lot (SYN-002), two products without demand (SYN-003, SYN-004) and one censored day.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from dashboard.drilldown import drilldown
from dashboard.filters import FilterSet
from dashboard.indicators import build_indicators
from dashboard.kpis import Filters, compute_summary
from db.tables import ALL_WAREHOUSES, demand_observations, products, stock_snapshots, variants
from reference_dataset import NOW, TODAY, freeze_clock, seed_reference
from sqlalchemy import insert


@pytest.fixture
def seeded(engine, monkeypatch):
    freeze_clock(monkeypatch)
    seed_reference(engine)
    return engine


def figures(engine):
    with engine.connect() as c:
        return {i["key"]: i for i in build_indicators(c, TODAY, FilterSet.parse(TODAY), None, ["buyer"], None, NOW)["indicators"]}


def add_product_with_stock(engine, external_id, sku, on_hand, daily_demand=1):
    with engine.begin() as c:
        c.execute(insert(products).values(external_id=external_id, name=sku, status="active", missed_syncs=0, clinical_critical=False))
        c.execute(insert(variants).values(external_id=external_id, product_id=external_id, sku=sku, name=sku, pack_size=1, uom="u", reorder_point=1, price=1))
        c.execute(insert(stock_snapshots).values(variant_id=external_id, warehouse_id=ALL_WAREHOUSES, snapshot_date=TODAY, on_hand=on_hand, available=on_hand, reserved=0))
        c.execute(insert(demand_observations).values([{"variant_id": external_id, "warehouse_id": 1, "day": TODAY - timedelta(days=i), "demand_qty": daily_demand, "censored": False, "lineage": "m"} for i in range(30)]))


@pytest.mark.parametrize("on_hand", [0, -3])
def test_a_product_with_no_stock_or_negative_stock_has_zero_days_of_cover_and_is_listed_first(seeded, on_hand):
    before = Decimal(figures(seeded)["coverage_days"]["value"])
    add_product_with_stock(seeded, 60, "SYN-060", on_hand)
    rows = figures(seeded)
    after = Decimal(rows["coverage_days"]["value"])
    assert rows["coverage_days"]["state"] == "ok" and after < before                      # the zero counts: it is never dropped from the average
    with seeded.connect() as c:
        out = drilldown(c, "coverage", TODAY, Filters(), limit=200)
    assert out["rows"][0]["sku"] == "SYN-060" and Decimal(out["rows"][0]["figure"]) == 0
    assert Decimal(rows["stock_value"]["value"]) == Decimal("100")                         # no lot, no value: stock value is untouched


def test_products_without_demand_are_counted_in_the_coverage_card_not_averaged_in(seeded):
    cov = figures(seeded)["coverage_days"]
    assert cov["incomplete_count"] == 3 and cov["state"] == "ok"                          # SYN-003, SYN-004 and SYN-005 have no demand to divide by


def test_an_estimated_cost_is_used_and_counted_and_a_lot_without_any_cost_is_left_out_and_counted(seeded):
    with seeded.connect() as c:
        s = compute_summary(c, TODAY)
    assert s.valued_with_estimate == 1 and s.unvalued_lots == 1 and s.inventory_value == Decimal("100")
    assert figures(seeded)["stock_value"]["incomplete_count"] == 1                          # the card says how many lots it could not value


def test_censored_days_are_counted_on_the_demand_card_and_left_out_of_its_figure(seeded):
    demand = figures(seeded)["demand"]
    assert demand["incomplete_count"] == 1 and demand["state"] == "ok" and Decimal(demand["value"]) == 239


def test_a_warehouse_without_sales_is_no_data_for_demand_never_zero(seeded):
    with seeded.connect() as c:
        rows = {i["key"]: i for i in build_indicators(c, TODAY, FilterSet.parse(TODAY, warehouse_id=2), None, ["buyer"], None, NOW)["indicators"]}
    assert rows["demand"]["state"] == "no_data" and rows["demand"]["value"] is None


def test_a_filter_that_matches_nothing_gives_no_data_everywhere_a_figure_would_be_a_total(seeded):
    with seeded.connect() as c:
        rows = {i["key"]: i for i in build_indicators(c, TODAY, FilterSet.parse(TODAY, supplier_id="sup-none"), None, ["buyer"], None, NOW)["indicators"]}
    assert rows["demand"]["state"] == "no_data" and rows["coverage_days"]["state"] == "no_data"
    assert rows["forecast"]["state"] == "no_data" and rows["forecast"]["value"] is None
