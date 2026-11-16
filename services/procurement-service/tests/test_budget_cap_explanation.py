"""T030 (FR-004, US4.1): with no deferral switched on (scenarios, and the allocator's default) a budget cap is a soft limit: every needed quantity stays, the excess is reported and each line is flagged. The weekly proposal may defer non-critical lines (feature 011 business policy, `test_budget_effect_011.py`)."""

from builders import flat_forecast, inputs, offer, terms, variant
from proposals.generate import generate


def catalogue(budget):
    vs = [variant(i, [offer("A", "1.00", pack=1)], flat_forecast(1.0), critical=(i == 1)) for i in (1, 2, 3)]
    return inputs(vs, [terms("A")], budget=budget)


def test_a_cap_below_the_total_keeps_every_quantity_and_reports_the_excess():
    free, tight = generate(catalogue("1000"), 10), generate(catalogue("12"), 10)
    assert [(ln.variant_id, ln.qty) for ln in tight.lines] == [(ln.variant_id, ln.qty) for ln in free.lines]      # nothing was cut
    assert free.over_budget == 0 and tight.over_budget == sum(g.total for g in tight.groups) - 12
    assert all("over_budget" in ln.explanation["constraints"] for ln in tight.lines) and all("over_budget" not in ln.explanation["constraints"] for ln in free.lines)


def test_the_clinically_critical_need_is_never_dropped_under_a_tight_cap():
    d = generate(catalogue("1"), 10)
    assert any(ln.variant_id == 1 and ln.qty > 0 for ln in d.lines)
