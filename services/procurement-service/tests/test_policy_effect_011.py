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
