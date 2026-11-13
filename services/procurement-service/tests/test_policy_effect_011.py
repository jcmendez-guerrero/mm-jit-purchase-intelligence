"""Feature 011 (T011, T030, T032): a saved policy changes the next proposal and not an earlier one; a budget cap binds it and its revision is recorded."""

from datetime import date
from decimal import Decimal

from conftest import NOW, add_supplier
from db.tables import proposals
from policies.service import PolicyValues, save_budget_cap, save_policy
from proposals.generate import generate, store
from proposals.inputs import InputsProvider
from sqlalchemy import select
from test_inputs import ELIGIBLE, Src, cost, fc, stock, sv

D = Decimal
TODAY = date(2026, 11, 9)


def provider():
    return InputsProvider(Src(stock(sv(1, 10, on_hand=0))), Src(fc(v1=ELIGIBLE)))


def quantity(conn) -> int:
    return sum(line.qty for line in generate(provider().build(conn, TODAY), 5).lines)


def test_a_saved_minimum_changes_the_next_proposal_and_not_the_stored_one(conn):
    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    before = quantity(conn)
    stored = store(conn, generate(provider().build(conn, TODAY), 5), "buyer-1", "2026-W46", None, NOW)
    save_policy(conn, "global", "*", PolicyValues(min_units=before + 40), "buyer-1", today=TODAY)
    assert quantity(conn) > before                                                       # the next proposal follows the policy
    assert not conn.execute(select(proposals.c.policy_version_ids).where(proposals.c.id == stored)).scalar()      # the stored one keeps what it used


def test_product_scope_wins_over_global_for_each_rule_independently(conn):
    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    save_policy(conn, "global", "*", PolicyValues(service_level=D("0.90"), min_units=5), "b", today=TODAY)
    save_policy(conn, "product", "1", PolicyValues(min_units=20), "b", today=TODAY)
    v = provider().build(conn, TODAY).variants[0]
    assert v.service_level == D("0.90") and v.min_units == 20                         # level from global, minimum from the product


def test_each_line_explanation_names_the_scope_and_the_revision_that_supplied_every_rule(conn):
    """T060, FR-004: not only where a value came from, but which version of it."""
    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    save_policy(conn, "global", "*", PolicyValues(service_level=D("0.90"), min_units=1), "b", today=TODAY)
    save_policy(conn, "global", "*", PolicyValues(service_level=D("0.91"), min_units=1), "b", expected_revision=1, today=TODAY)          # global is at revision 2
    save_policy(conn, "segment", "B", PolicyValues(service_level=D("0.97")), "b", today=TODAY)                                          # the product's class
    save_policy(conn, "product", "1", PolicyValues(max_units=500), "b", today=TODAY)
    applied = generate(provider().build(conn, TODAY), 5).lines[0].explanation["policy_applied"]
    assert applied["service_level"] == {"source": "segment:B", "revision": 1}
    assert applied["min_units"] == {"source": "global:*", "revision": 2}
    assert applied["max_units"] == {"source": "product:1", "revision": 1}
    assert "safety_stock_units" not in applied                                                    # nothing set: the computed default applies, nothing to cite


def build_draft(conn, *variants):
    """A proposal for the given stock variants (all with the same cost, forecast and zero stock)."""
    sa = add_supplier(conn, 1, "A")
    for v in variants:
        cost(conn, sa, v["product_id"], "1.00")
    provider = InputsProvider(Src(stock(*variants)), Src(fc(**{f"v{v['variant_id']}": ELIGIBLE for v in variants})))
    return provider


def qty_of(draft, variant_id=1):
    return {ln.variant_id: ln.qty for ln in draft.lines}.get(variant_id, 0)


def test_a_saved_safety_stock_changes_the_next_quantity_and_is_the_safety_stock_explained(conn):
    """T061: one saved rule per test, each proven to move the next calculation, and each cited with its revision."""
    provider = build_draft(conn, sv(1, 10, on_hand=0))
    before = generate(provider.build(conn, TODAY), 5)
    save_policy(conn, "global", "*", PolicyValues(safety_stock_units=60), "b", today=TODAY)
    after = generate(provider.build(conn, TODAY), 5)
    assert qty_of(after) > qty_of(before)
    assert after.lines[0].safety_stock == 60 and after.lines[0].explanation["policy_applied"]["safety_stock_units"] == {"source": "global:*", "revision": 1}


def test_a_saved_maximum_caps_the_next_quantity(conn):
    provider = build_draft(conn, sv(1, 10, on_hand=0))
    before = qty_of(generate(provider.build(conn, TODAY), 5))
    save_policy(conn, "global", "*", PolicyValues(max_units=5), "b", today=TODAY)
    after = generate(provider.build(conn, TODAY), 5)
    assert 0 < qty_of(after) <= 5 < before
    assert after.lines[0].explanation["policy_applied"]["max_units"] == {"source": "global:*", "revision": 1}


def test_a_saved_replenishment_cadence_changes_the_protection_horizon_and_the_quantity(conn):
    """T061: the cadence is the review period; it was stored and shown but nothing read it."""
    provider = build_draft(conn, sv(1, 10, on_hand=0))
    before = generate(provider.build(conn, TODAY), 5)
    save_policy(conn, "global", "*", PolicyValues(replenishment_cadence_days=21), "b", today=TODAY)
    after = generate(provider.build(conn, TODAY), 5)
    assert after.lines[0].explanation["horizon_days"] == before.lines[0].explanation["horizon_days"] + 14          # 21-day review period instead of the default 7
    assert qty_of(after) > qty_of(before)
    assert after.lines[0].explanation["policy_applied"]["replenishment_cadence_days"] == {"source": "global:*", "revision": 1}


def test_a_shorter_cadence_shortens_the_horizon_and_a_product_cadence_beats_the_global_one(conn):
    provider = build_draft(conn, sv(1, 10, on_hand=0), sv(2, 11, on_hand=0))
    save_policy(conn, "global", "*", PolicyValues(replenishment_cadence_days=3), "b", today=TODAY)
    save_policy(conn, "product", "2", PolicyValues(replenishment_cadence_days=28), "b", today=TODAY)
    horizons = {ln.variant_id: ln.explanation["horizon_days"] for ln in generate(provider.build(conn, TODAY), 5).lines}
    assert horizons[2] - horizons[1] == 25                                                           # 28 days for the product, 3 for everything else


def test_clinical_criticality_selects_the_critical_segment_policy_for_that_product_only(conn):
    """T061 (US3/AC2): marking a product critical changes which policy applies to it."""
    provider = build_draft(conn, sv(1, 10, on_hand=0, critical=True), sv(2, 11, on_hand=0))
    plain = generate(provider.build(conn, TODAY), 5)
    save_policy(conn, "segment", "critical", PolicyValues(min_units=80, service_level=D("0.99")), "b", today=TODAY)
    after = generate(provider.build(conn, TODAY), 5)
    assert qty_of(after, 1) >= 80 > qty_of(plain, 1) and qty_of(after, 2) == qty_of(plain, 2)       # only the critical product follows the critical policy
    assert after.lines[0].explanation["policy_applied"]["min_units"] == {"source": "segment:critical", "revision": 1}


def test_a_budget_cap_binds_the_next_proposal(conn):
    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    free = generate(provider().build(conn, TODAY), 5)
    total = sum((line.line_total for line in free.lines), D(0))
    assert total > 0
    save_budget_cap(conn, "week", "global", None, total / 2, "buyer-1", today=TODAY)
    capped_inputs = provider().build(conn, TODAY)
    assert capped_inputs.budget is not None and capped_inputs.budget < total
    capped = generate(capped_inputs, 5)
    assert sum((line.line_total for line in capped.lines), D(0)) <= total                 # never more than without the cap
    assert capped.over_budget >= 0


def test_the_budget_cap_revision_is_recorded_with_the_policy_versions(conn):
    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    save_budget_cap(conn, "week", "global", None, D("500"), "b", today=TODAY, expected_revision=0)
    save_budget_cap(conn, "week", "global", None, D("400"), "b", today=TODAY, expected_revision=1)
    inputs = provider().build(conn, TODAY)
    assert inputs.policy_versions["budget:week:global:*"] == 2
    pid = store(conn, generate(inputs, 5), "buyer-1", "2026-W46", None, NOW)
    assert conn.execute(select(proposals.c.policy_version_ids).where(proposals.c.id == pid)).scalar()["budget:week:global:*"] == 2
