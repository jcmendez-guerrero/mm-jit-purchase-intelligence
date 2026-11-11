"""Feature 011 (T059, FR-019, US3 AC1-AC3): a binding cap defers the least urgent non-critical lines and says so, never drops a critical product silently, and names the cap that bound."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from conftest import add_supplier
from policies.service import save_budget_cap
from proposals.generate import generate
from proposals.inputs import InputsProvider
from proposals.model import Overrides
from test_inputs import ELIGIBLE, Src, cost, fc, stock, sv

D = Decimal
TODAY = date(2026, 11, 9)


def setup(conn):
    """Three products with the same need and the same cost at one supplier; variant 1 is clinically critical."""
    sa = add_supplier(conn, 1, "A")
    for pid in (10, 11, 12):
        cost(conn, sa, pid, "1.00")
    provider = InputsProvider(Src(stock(sv(1, 10, on_hand=0, critical=True), sv(2, 11, on_hand=0), sv(3, 12, on_hand=0))), Src(fc(v1=ELIGIBLE, v2=ELIGIBLE, v3=ELIGIBLE)))
    free = generate(provider.build(conn, TODAY), 5)
    line = {ln.variant_id: ln.line_total for ln in free.lines}
    assert set(line) == {1, 2, 3}
    return sa, provider, line, sum(line.values(), D(0))


def kept(draft):
    return {ln.variant_id for ln in draft.lines}


def test_a_cap_that_binds_defers_non_critical_lines_lists_them_with_the_reason_and_stays_within_it(conn):
    sa, provider, line, total = setup(conn)
    save_budget_cap(conn, "week", "global", None, line[1] + line[2] + D("0.5"), "b", today=TODAY)          # room for two of the three lines
    draft = generate(provider.build(conn, TODAY), 5)
    assert 1 in kept(draft) and len(kept(draft)) == 2                                                    # the critical product stays
    assert sum((ln.line_total for ln in draft.lines), D(0)) <= line[1] + line[2] + D("0.5") and draft.over_budget == 0
    (deferred,) = draft.deferred
    assert deferred["variant_id"] in {2, 3} and deferred["reason"] == "budget_cap" and deferred["bound_by"] == ["global_week"]
    assert deferred["variant_id"] not in kept(draft)


def test_a_critical_product_is_never_dropped_and_the_excess_is_shown_for_decision(conn):
    sa, provider, line, total = setup(conn)
    save_budget_cap(conn, "week", "global", None, line[1] / 4, "b", today=TODAY)                          # below the cost of the critical line alone
    draft = generate(provider.build(conn, TODAY), 5)
    assert kept(draft) == {1}                                                                           # both non-critical lines are deferred, the critical one stays
    assert {d["variant_id"] for d in draft.deferred} == {2, 3}
    assert draft.over_budget > 0 and "over_budget" in draft.lines[0].constraints
    assert "critical_over_budget" in draft.notes


def test_nothing_is_deferred_when_no_cap_binds(conn):
    sa, provider, line, total = setup(conn)
    save_budget_cap(conn, "week", "global", None, total * 2, "b", today=TODAY)
    draft = generate(provider.build(conn, TODAY), 5)
    assert kept(draft) == {1, 2, 3} and draft.deferred == () and not [n for n in draft.notes if n.startswith("budget_bound")]


def test_the_cap_that_bound_is_named_weekly_or_monthly(conn):
    sa, provider, line, total = setup(conn)
    save_budget_cap(conn, "week", "global", None, total * 2, "b", today=TODAY)                           # a loose weekly cap
    save_budget_cap(conn, "month", "global", None, (line[1] + line[2]) * D("4.33"), "b", today=TODAY)     # a tighter monthly cap, about two lines a week
    draft = generate(provider.build(conn, TODAY), 5)
    assert "budget_bound:global_month" in draft.notes and "budget_bound:global_week" not in draft.notes
    assert len(kept(draft)) == 2 and draft.deferred[0]["bound_by"] == ["global_month"]


def test_a_supplier_cap_tighter_than_the_global_one_is_the_one_that_binds(conn):
    sa, provider, line, total = setup(conn)
    save_budget_cap(conn, "week", "global", None, total * 2, "b", today=TODAY)
    save_budget_cap(conn, "week", "supplier", sa, line[1] + line[2] + D("0.5"), "b", today=TODAY)
    draft = generate(provider.build(conn, TODAY), 5)
    assert len(kept(draft)) == 2 and 1 in kept(draft)
    assert f"budget_bound:supplier:{sa}" in draft.notes and "budget_bound:global_week" not in draft.notes
    assert draft.deferred[0]["bound_by"] == [f"supplier:{sa}"]


def test_the_global_cap_is_the_one_named_when_it_is_the_tighter(conn):
    sa, provider, line, total = setup(conn)
    save_budget_cap(conn, "week", "global", None, line[1] + line[2] + D("0.5"), "b", today=TODAY)
    save_budget_cap(conn, "week", "supplier", sa, total * 2, "b", today=TODAY)
    draft = generate(provider.build(conn, TODAY), 5)
    assert len(kept(draft)) == 2 and "budget_bound:global_week" in draft.notes and f"budget_bound:supplier:{sa}" not in draft.notes


def test_the_stored_proposal_lists_deferred_lines_by_sku_and_names_the_caps_without_ids(conn):
    from api.proposals import proposal_json
    from conftest import NOW
    from db.tables import proposals
    from proposals.generate import store
    from sqlalchemy import select

    sa, provider, line, total = setup(conn)                                                 # building the inputs also records each product's SKU and name
    save_budget_cap(conn, "week", "global", None, line[1] + D("0.5"), "b", today=TODAY)
    save_budget_cap(conn, "week", "supplier", sa, total * 2, "b", today=TODAY)
    pid = store(conn, generate(provider.build(conn, TODAY), 5), "buyer-1", "2026-W46", None, NOW)
    view = proposal_json(conn, conn.execute(select(proposals).where(proposals.c.id == pid)).first())["flags"]
    assert {d["sku"] for d in view["deferred"]} == {"SYN-2", "SYN-3"} and all(d["reason"] == "budget_cap" for d in view["deferred"])
    assert view["deferred"][0]["product_name"].startswith("Producto") and view["deferred"][0]["bound_by"] == [{"kind": "global_week"}]
    assert all("variant_id" not in d and "product_id" not in d for d in view["deferred"])


def test_a_scenario_built_on_live_inputs_still_reports_an_unaffordable_budget_instead_of_cutting_lines(conn):
    from scenarios.engine import ScenarioParams, apply_params

    sa, provider, line, total = setup(conn)
    base = provider.build(conn, TODAY)
    assert base.defer_for_cap                                                                           # the weekly proposal may defer
    scenario = apply_params(base, ScenarioParams(budget=line[1] / 4))
    assert not scenario.defer_for_cap
    draft = generate(scenario, 5)
    assert kept(draft) == {1, 2, 3} and draft.deferred == () and draft.over_budget > 0                  # all lines kept, the excess reported


def test_a_line_the_buyer_fixed_is_not_deferred_by_the_cap(conn):
    sa, provider, line, total = setup(conn)
    save_budget_cap(conn, "week", "global", None, line[1] / 4, "b", today=TODAY)
    inputs = replace(provider.build(conn, TODAY), overrides=Overrides(fixed_qty={2: 5}))                # the buyer asked for 5 units of variant 2
    draft = generate(inputs, 5)
    assert {1, 2} <= kept(draft) and 3 not in kept(draft)
