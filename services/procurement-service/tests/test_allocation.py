"""T084: allocation respects minimums, thresholds, pack multiples, budget and overrides (property + scenario tests)."""

from decimal import Decimal

from allocation.common import build_lines
from allocation.cpsat import allocate_cpsat
from allocation.greedy import allocate_greedy
from allocation.shortfall import options_for
from builders import flat_forecast, inputs, offer, terms, variant
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from proposals.model import Overrides, money, ticks

D = Decimal


def solve(inp, **kw):
    lines = build_lines(inp)
    return lines, allocate_greedy(inp, lines), allocate_cpsat(inp, lines, time_limit_s=10, **kw)


def by_variant(alloc):
    return {c.variant_id: c for c in alloc.chosen}


def test_the_cheapest_eligible_supplier_wins_when_there_are_no_terms():
    inp = inputs([variant(1, [offer("A", "2.00"), offer("B", "1.50")])], [terms("A"), terms("B")])
    _, greedy, opt = solve(inp)
    assert by_variant(opt)[1].supplier_id == "B" == by_variant(greedy)[1].supplier_id and opt.solver_status == "optimal"


def test_quantities_are_rounded_up_to_the_pack_and_the_minimum_order_quantity():
    inp = inputs([variant(1, [offer("A", "1", pack=12, moq=0)], on_hand=0), variant(2, [offer("A", "1", pack=1, moq=40)], on_hand=0)], [terms("A")])
    _, _, opt = solve(inp)
    q = by_variant(opt)
    assert q[1].qty % 12 == 0 and q[1].qty >= 24 and q[2].qty >= 40


def test_free_delivery_threshold_can_make_a_dearer_supplier_cheaper_overall():
    # A is cheaper per unit but charges 20 EUR delivery; B is 10 % dearer with free delivery over 100 EUR
    inp = inputs([variant(1, [offer("A", "1.00"), offer("B", "1.10")])], [terms("A", charge="20"), terms("B", free="100", charge="20")])
    _, _, opt = solve(inp)
    line = by_variant(opt)[1]
    assert line.supplier_id == "A"                  # one 20-unit order: 20 + 20 delivery < 22 + 20 delivery
    inp2 = inputs([variant(1, [offer("A", "1.00"), offer("B", "1.10")], flat_forecast(4.0)), variant(2, [offer("B", "1.00")], flat_forecast(6.0))],
                  [terms("A", charge="20"), terms("B", free="100", charge="20")])
    _, _, opt2 = solve(inp2)
    q = by_variant(opt2)
    assert q[1].supplier_id == "B" and q[2].supplier_id == "B"                    # bundled with variant 2 reaches the threshold
    assert next(g for g in opt2.groups if g.supplier_id == "B").free_delivery
    assert opt2.total_ticks <= allocate_greedy(inp2, build_lines(inp2)).total_ticks


def test_a_minimum_order_value_is_reached_by_topping_up_needed_soon_items():
    inp = inputs([variant(1, [offer("A", "1.00")], on_hand=0), variant(2, [offer("A", "1.00")], on_hand=500, soon=50)], [terms("A", min_value="60")])
    lines = build_lines(inp)
    opt = allocate_cpsat(inp, lines, time_limit_s=10)
    q = by_variant(opt)
    assert 2 in q and q[2].topup and opt.groups[0].minimum_status == "met"
    assert opt.groups[0].subtotal_ticks >= ticks(D("60"))


def test_an_unreachable_minimum_is_flagged_not_hidden_and_options_show_the_cost_impact():
    inp = inputs([variant(1, [offer("A", "1.00"), offer("B", "1.30")], flat_forecast(1.0))], [terms("A", min_value="500"), terms("B")])
    lines = build_lines(inp)
    opt = allocate_cpsat(inp, lines, time_limit_s=10)
    assert by_variant(opt)[1].supplier_id == "B"                                    # moves to the supplier without a minimum
    inp2 = inputs([variant(1, [offer("A", "1.00")], flat_forecast(1.0))], [terms("A", min_value="500")])
    lines2 = build_lines(inp2)
    opt2 = allocate_cpsat(inp2, lines2, time_limit_s=10)
    g = opt2.groups[0]
    assert g.minimum_status == "shortfall" and g.shortfall_value_ticks > 0
    kinds = {o.kind for o in options_for(inp2, lines2, opt2)}
    assert kinds == {"accept"}
    inp3 = inputs([variant(1, [offer("A", "1.00"), offer("B", "1.30")], flat_forecast(1.0), ), variant(2, [offer("A", "1.00")], on_hand=500, soon=10)],
                  [terms("A", min_value="500"), terms("B")], overrides=Overrides(fixed_supplier={1: "A"}))
    lines3 = build_lines(inp3)
    opt3 = allocate_cpsat(inp3, lines3, time_limit_s=10)
    opts = options_for(inp3, lines3, opt3)
    assert {o.kind for o in opts} >= {"reallocate", "accept"} and all(isinstance(o.cost_delta_ticks, int) for o in opts)


def test_minimum_quantity_for_delivery():
    inp = inputs([variant(1, [offer("A", "1.00"), offer("B", "1.40")], flat_forecast(1.0))], [terms("A", min_qty=500), terms("B")])
    _, _, opt = solve(inp)
    assert by_variant(opt)[1].supplier_id == "B"


def test_budget_is_respected_when_possible_and_flagged_when_not():
    inp = inputs([variant(1, [offer("A", "1.00")])], [terms("A")], budget="10000")
    assert solve(inp)[2].over_budget_ticks == 0
    tight = inputs([variant(1, [offer("A", "1.00")])], [terms("A")], budget="5")
    assert solve(tight)[2].over_budget_ticks > 0


def test_overrides_fix_supplier_and_quantity_and_exclusions_are_honoured():
    base = [variant(1, [offer("A", "1.00"), offer("B", "2.00")])]
    _, _, o1 = solve(inputs(base, [terms("A"), terms("B")], overrides=Overrides(fixed_supplier={1: "B"})))
    assert by_variant(o1)[1].supplier_id == "B"
    _, _, o2 = solve(inputs(base, [terms("A"), terms("B")], overrides=Overrides(fixed_qty={1: 77})))
    assert by_variant(o2)[1].qty == 77
    _, _, o3 = solve(inputs(base, [terms("A"), terms("B")], overrides=Overrides(excluded={1: frozenset({"A"})})))
    assert by_variant(o3)[1].supplier_id == "B"


def test_blocked_costs_and_slow_suppliers_are_never_offered():
    inp = inputs([variant(1, [offer("A", "0.10", status="blocked_jump"), offer("B", "1.00", lead=30), offer("C", "3.00")])], [terms("A"), terms("B"), terms("C")])
    lines = build_lines(inp)
    assert [c.supplier_id for c in lines[0].cands] == ["C"] and {r for _, r in lines[0].rejected} == {"cost_blocked", "lead_time_too_long"}


def test_lines_with_no_need_are_not_ordered():
    inp = inputs([variant(1, [offer("A", "1")], on_hand=1000)], [terms("A")])
    assert solve(inp)[2].chosen == []


def test_result_is_deterministic():
    inp = inputs([variant(i, [offer("A", f"{1 + i / 10:.2f}"), offer("B", f"{1.5 - i / 10:.2f}")], flat_forecast(2.0 + i)) for i in range(1, 6)],
                 [terms("A", min_value="30", charge="5"), terms("B", free="80", charge="8")])
    first, second = solve(inp)[2], solve(inp)[2]
    assert first.chosen == second.chosen and first.groups == second.groups


# ---- properties -----------------------------------------------------------------------------------------

offers_st = st.lists(st.tuples(st.sampled_from(["A", "B", "C"]), st.integers(50, 500), st.sampled_from([1, 6, 12]), st.integers(0, 14), st.sampled_from([0, 0, 20])),
                     min_size=1, max_size=3, unique_by=lambda t: t[0])
variant_st = st.tuples(offers_st, st.integers(0, 60), st.integers(1, 6))
terms_st = st.fixed_dictionaries({"min_value": st.sampled_from([None, "20", "80"]), "min_qty": st.sampled_from([None, 10, 40]),
                                  "free": st.sampled_from([None, "60", "200"]), "charge": st.sampled_from([None, "5", "12.5"])})


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(variant_st, min_size=1, max_size=5), terms_st, terms_st, terms_st, st.sampled_from([None, "50", "400", "100000"]))
def test_allocation_invariants(vs, ta, tb, tc, budget):
    variants = []
    for i, (offs, on_hand, rate) in enumerate(vs, start=1):
        variants.append(variant(i, [offer(s, f"{c / 100:.2f}", pack=p, lead=ld, moq=m) for s, c, p, ld, m in offs], flat_forecast(float(rate)), on_hand=on_hand))
    sup = [terms("A", **ta), terms("B", **tb), terms("C", **tc)]
    inp = inputs(variants, sup, budget=budget)
    lines = build_lines(inp)
    greedy, opt = allocate_greedy(inp, lines), allocate_cpsat(inp, lines, time_limit_s=10)
    spec = {ln.variant_id: ln for ln in lines}
    chosen = by_variant(opt)
    for ln in lines:
        if ln.mandatory and ln.cands:
            assert ln.variant_id in chosen                                    # every needed line is ordered exactly once
    assert len(chosen) == len(opt.chosen)
    for c in opt.chosen:
        o = next(x.offer for x in spec[c.variant_id].cands if x.supplier_id == c.supplier_id)
        assert c.qty % o.pack_size == 0 and c.qty >= o.min_order_qty and c.qty > 0     # pack multiples and MOQ
        assert c.line_ticks == c.qty * c.unit_ticks
    terms_by = {t.supplier_id: t for t in sup}
    for g in opt.groups:
        t = terms_by[g.supplier_id]
        if g.minimum_status == "met":
            assert t.min_order_value is None or g.subtotal_ticks >= ticks(t.min_order_value)
            assert not t.min_qty_for_delivery or g.qty >= t.min_qty_for_delivery
        if t.free_delivery_threshold is not None:
            assert g.free_delivery == (g.subtotal_ticks >= ticks(t.free_delivery_threshold))
        if g.free_delivery:
            assert g.delivery_charge_ticks == 0
        elif t.delivery_charge is not None:
            assert g.delivery_charge_ticks == ticks(t.delivery_charge)
    if all(g.minimum_status == "met" for g in greedy.groups) and greedy.over_budget_ticks == 0 and opt.solver_status in ("optimal", "feasible"):
        assert opt.total_ticks <= greedy.total_ticks                                  # never worse than the baseline
        assert opt.over_budget_ticks == 0
    if budget is not None and all(g.minimum_status == "met" for g in greedy.groups) and greedy.over_budget_ticks == 0 and opt.solver_status == "optimal":
        assert sum(g.total_ticks for g in opt.groups) <= ticks(D(budget))      # a plan inside the budget exists, so the optimum stays inside


def test_money_helpers_round_trip():
    assert money(ticks(D("2.4196"))) == D("2.4196")
