"""T004: the reference dataset reproduces the totals documented in TOTALS.md with the current summary code."""

from decimal import Decimal

from dashboard.kpis import Filters, compute_summary
from reference_dataset import TODAY, seed_reference

D = Decimal


def test_unfiltered_totals_match_the_documented_expectation(engine):
    seed_reference(engine)
    with engine.connect() as c:
        s = compute_summary(c, TODAY)
    assert s.inventory_value == D("92") and s.expiring_value == D("60.00")
    assert s.valued_with_estimate == 1 and s.unvalued_lots == 1


def test_warehouse_totals_match_the_documented_expectation(engine):
    seed_reference(engine)
    with engine.connect() as c:
        w1 = compute_summary(c, TODAY, Filters(warehouse_id=1))
        w2 = compute_summary(c, TODAY, Filters(warehouse_id=2))
    assert (w1.inventory_value, w1.expiring_value) == (D("32"), D("0"))
    assert (w2.inventory_value, w2.expiring_value) == (D("60"), D("60.00"))
    assert w1.valued_with_estimate == 1 and w1.unvalued_lots == 1 and w2.valued_with_estimate == 0 and w2.unvalued_lots == 0
