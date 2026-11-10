"""T028 (feature 006): each filter and the combinations change every indicator to the expected subset; the supplier filter is the supplier of the lot cost.

Expected figures are the independently computed ones in the synthetic reference dataset (TOTALS.md), not read back from the code. Demand over the 60 days:
SYN-001 (A, sup-a) 180, SYN-002 (B, sup-b fallback) 59, the others none.
"""

from decimal import Decimal

import pytest
from dashboard.filters import FilterSet
from dashboard.indicators import build_indicators
from dashboard.kpis import refresh_aggregates
from reference_dataset import NOW, TODAY, seed_reference

# filters -> (stock value, expiring value, demand units or None)
MATRIX = [
    ({}, "100.00", "60.00", "239"),
    ({"supplier_id": "sup-a"}, "42.00", "20.00", "180"),
    ({"supplier_id": "sup-b"}, "58.00", "40.00", "59"),
    ({"warehouse_id": 1}, "40.00", "0.00", "239"),
    ({"warehouse_id": 2}, "60.00", "60.00", None),
    ({"category": "A"}, "40.00", "20.00", "180"),
    ({"category": "B"}, "20.00", "0.00", "59"),
    ({"category": "C"}, "40.00", "40.00", None),
    ({"category": "critical"}, "40.00", "40.00", None),
    ({"supplier_id": "sup-a", "category": "B"}, "2.00", "0.00", None),
    ({"supplier_id": "sup-a", "warehouse_id": 2}, "20.00", "20.00", None),
]


@pytest.fixture
def seeded(engine):
    seed_reference(engine)
    with engine.begin() as c:
        refresh_aggregates(c, TODAY, None, NOW)
    return engine


def indicators(engine, **filters):
    with engine.connect() as c:
        return {i["key"]: i for i in build_indicators(c, TODAY, FilterSet.parse(TODAY, **filters), None, ("buyer",), Decimal("0.00"))["indicators"]}


@pytest.mark.parametrize("filters,stock,expiring,demand", MATRIX, ids=[str(m[0]) for m in MATRIX])
def test_each_filter_and_combination_gives_the_expected_subset(seeded, filters, stock, expiring, demand):
    i = indicators(seeded, **filters)
    assert i["stock_value"]["value"] == stock and i["expiry_exposure"]["value"] == expiring
    assert i["capital_tied_up"]["value"] == stock                                      # no open orders: capital is the stock at cost
    assert i["demand"]["value"] == demand and (i["demand"]["state"] == "ok") == (demand is not None)


def test_the_supplier_is_the_one_of_the_lot_cost_and_the_two_suppliers_add_up_to_the_whole(seeded):
    # SYN-004 has an old sup-a cost row without stock: it counts for sup-b only; SYN-005 splits its two lots between both
    a, b = (Decimal(indicators(seeded, supplier_id=s)["stock_value"]["value"]) for s in ("sup-a", "sup-b"))
    # the unvalued lot has no supplier, so it adds nothing to either side
    assert a + b == Decimal(indicators(seeded)["stock_value"]["value"])


def test_a_supplier_without_stock_gives_no_demand_and_not_zero(seeded):
    i = indicators(seeded, supplier_id="nobody")
    assert i["demand"]["value"] is None and i["demand"]["state"] == "no_data"
