"""T074 (Constitution III): a line never says "lower total" when the plan as a whole costs more cash than the baseline.

The optimiser minimises cash plus lead-time risk, so it may pay a little more to avoid a slow supplier. The line must then say that.
"""

from __future__ import annotations

from builders import flat_forecast, inputs, offer, terms, variant
from proposals.generate import generate


def reasons(charge_b: str, lead_b: int) -> dict[int, str]:
    variants = [variant(1, [offer("A", "0.50")], flat_forecast(1.0), on_hand=0),
                variant(2, [offer("A", "1.03", pack=12), offer("B", "0.50", lead=lead_b)], flat_forecast(2.0), on_hand=0)]
    draft = generate(inputs(variants, [terms("A"), terms("B", charge=charge_b)]), 5)
    return {ln.variant_id: ln.explanation["supplier"]["reason"] for ln in draft.lines}


def test_a_plan_that_pays_more_cash_to_avoid_a_slow_supplier_says_so():
    out = reasons("12.5", lead_b=5)
    assert out[2] == "lower_lead_time_risk"


def test_a_plan_that_really_costs_less_keeps_the_lower_total_reason():
    out = reasons("100", lead_b=0)                       # B's delivery charge makes B dearer overall; no lead-time difference
    assert out[2] == "lower_total_with_supplier_terms"
