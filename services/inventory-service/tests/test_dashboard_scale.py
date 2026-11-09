"""T092 (SC-003, plan: scale): the main dashboard operations stay under 2 seconds at about 20,000 variants.

Each variant has one costed lot; a tenth of them have 60 days of demand; two suppliers share the stock evenly. Budgets are for this in-memory database on a development machine,
so a failure means the work grew, not that the machine is slow.
"""

import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from dashboard.drilldown import drilldown
from dashboard.kpis import Filters, compute_summary, demand_summary, forecast_summary
from db.tables import (
    ALL_WAREHOUSES,
    demand_observations,
    lot_cost_projection,
    products,
    stock_lots,
    stock_snapshots,
    variants,
)
from sqlalchemy import insert

TODAY = date(2026, 11, 9)
NOW = datetime(2026, 11, 9, 8, tzinfo=UTC)
VARIANTS = 20_000
SELLERS = 2_000
BUDGET_SECONDS = 2.0


class Means:
    def __init__(self, m):
        self.m = m

    def daily_means(self):
        return self.m


@pytest.fixture
def big(engine):
    ids = range(1, VARIANTS + 1)
    with engine.begin() as c:
        c.execute(insert(products), [{"external_id": 1, "name": "P", "status": "active", "missed_syncs": 0, "clinical_critical": False}])
        c.execute(insert(variants), [{"external_id": i, "product_id": 1, "sku": f"SYN-{i:05d}", "name": f"V{i}", "pack_size": 1, "uom": "u", "reorder_point": 2, "price": 5} for i in ids])
        c.execute(insert(stock_lots), [{"variant_id": i, "warehouse_id": 1, "batch_number": "L", "expiry_date": TODAY + timedelta(days=30 * (i % 20)), "quantity": 5, "seen_at": NOW} for i in ids])
        c.execute(insert(lot_cost_projection), [{"variant_id": i, "supplier_id": "sup-a" if i % 2 else "sup-b", "lot": "L", "unit_cost": Decimal("2.00"), "source": "confirmed_order",
                                                 "updated_at": NOW} for i in ids])
        c.execute(insert(stock_snapshots), [{"variant_id": i, "warehouse_id": ALL_WAREHOUSES, "snapshot_date": TODAY, "on_hand": 5, "available": 5, "reserved": 0} for i in ids])
        c.execute(insert(demand_observations), [{"variant_id": i, "warehouse_id": 1, "day": TODAY - timedelta(days=d), "demand_qty": 1, "censored": False, "lineage": "m"}
                                                for i in range(1, SELLERS + 1) for d in range(60)])
    return engine


def timed(engine, fn):
    t0 = time.perf_counter()
    with engine.connect() as c:
        out = fn(c)
    return out, time.perf_counter() - t0


def test_the_summary_demand_forecast_supplier_filter_and_first_drill_page_each_stay_under_two_seconds(big):
    means = Means({i: 1.0 for i in range(1, SELLERS + 1)})
    results = {
        "summary": timed(big, lambda c: compute_summary(c, TODAY)),
        "demand": timed(big, lambda c: demand_summary(c, TODAY, 60, Filters())),
        "forecast": timed(big, lambda c: forecast_summary(c, TODAY, Filters(), means)),
        "supplier": timed(big, lambda c: compute_summary(c, TODAY, Filters(supplier_id="sup-a"))),
        "drill": timed(big, lambda c: drilldown(c, "inventory_value", TODAY, Filters(), limit=50)),
    }
    slow = {k: round(t, 2) for k, (_out, t) in results.items() if t >= BUDGET_SECONDS}
    print("scale timings (s):", {k: round(t, 2) for k, (_out, t) in results.items()})        # visible with -s, to see the margin
    assert slow == {}, f"over {BUDGET_SECONDS}s: {slow}"
    # the answers are right at this size too
    assert results["summary"][0].inventory_value == Decimal("200000.00")
    assert results["demand"][0]["units"] == SELLERS * 60
    assert results["forecast"][0]["units"] == str((Decimal(SELLERS) * 28).quantize(Decimal("0.01")))
    assert results["supplier"][0].inventory_value == Decimal("100000.00")
    assert results["drill"][0]["total"] == VARIANTS and len(results["drill"][0]["rows"]) == 50
