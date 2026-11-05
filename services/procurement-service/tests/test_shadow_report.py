"""Tests for T128: shadow-mode report."""

from decimal import Decimal

from proposals.shadow_report import generate_shadow_report


def test_shadow_report_computes_variance_and_override_rate():
    recs = [
        {"variant_id": 1, "recommended_qty": 10, "recommended_cost": "100.00"},
        {"variant_id": 2, "recommended_qty": 5, "recommended_cost": "50.00"},
        {"variant_id": 3, "recommended_qty": 20, "recommended_cost": "200.00"},
    ]
    actuals = [
        {"variant_id": 1, "actual_qty": 10, "actual_cost": "100.00"},  # accepted
        {"variant_id": 2, "actual_qty": 0, "actual_cost": "0.00"},      # overridden (skipped)
        {"variant_id": 3, "actual_qty": 30, "actual_cost": "300.00"},   # overridden (increased)
    ]
    stockouts = {2}  # variant 2 skipped by buyer suffered a stockout!

    report = generate_shadow_report(recs, actuals, stockout_variants=stockouts)

    assert report.total_variants_evaluated == 3
    assert report.overridden_count == 2
    assert report.override_rate == Decimal("0.6667")
    assert report.total_recommended_cost == Decimal("350.00")
    assert report.total_actual_cost == Decimal("400.00")
    assert report.cost_variance == Decimal("50.00")
    assert report.stockout_incidents == 1

    var2 = next(l for l in report.lines if l.variant_id == 2)
    assert var2.overridden is True
    assert var2.qty_difference == -5
    assert var2.stockout_occurred is True
