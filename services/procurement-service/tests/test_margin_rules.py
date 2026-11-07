"""T061: margin = 1 - cost / PVP and the rules of FR-043."""

from decimal import Decimal

import pytest
from costs.margin import (
    ABOVE_CAP,
    BELOW_MINIMUM,
    KEPT_OFFER,
    UNAVAILABLE,
    cap_for,
    cost_for_margin,
    evaluate,
    margin_of,
)

D = Decimal


def test_margin_formula_and_its_inverse():
    assert margin_of(D("7.00"), D("10.00")) == D("0.3000")
    assert margin_of(D("10.00"), D("10.00")) == D("0.0000")
    assert cost_for_margin(D("10.00"), D("0.15")) == D("8.5000") and cost_for_margin(D("10.00"), D("0.30")) == D("7.0000")
    assert margin_of(D("1"), None) is None and margin_of(D("1"), D("0")) is None


def test_the_cap_depends_on_the_cost_with_the_threshold_at_exactly_50():
    assert cap_for(D("49.9999")) == D("0.30") and cap_for(D("50")) == D("0.20") and cap_for(D("120")) == D("0.20")


def test_exactly_15_percent_is_allowed_and_one_cent_more_cost_is_blocked():
    pvp = D("10.00")
    at_floor = evaluate(D("8.50"), D("8.00"), pvp)
    assert not at_floor.blocked and BELOW_MINIMUM not in at_floor.flags and at_floor.margin_after == D("0.1500")
    over = evaluate(D("8.51"), D("8.00"), pvp)
    assert over.blocked and BELOW_MINIMUM in over.flags


def test_a_margin_exactly_at_the_cap_has_no_flag_and_below_the_cap_cost_is_flagged():
    pvp = D("10.00")
    assert evaluate(D("7.00"), D("8.00"), pvp).flags == ()                  # exactly 30 %
    assert evaluate(D("6.99"), D("8.00"), pvp).flags == (ABOVE_CAP,)         # 30.1 %, was 20 %: increase up to the cap, excess flagged


def test_a_margin_already_at_or_above_the_cap_is_kept_and_labelled_an_offer():
    pvp = D("10.00")
    e = evaluate(D("6.00"), D("7.00"), pvp)                                  # was exactly 30 %, now 40 %
    assert e.flags == (KEPT_OFFER,) and not e.blocked
    assert evaluate(D("6.00"), D("5.00"), pvp).flags == (KEPT_OFFER,)        # was 50 %
    assert evaluate(D("6.00"), None, pvp).flags == (ABOVE_CAP,)              # no previous cost: nothing was kept


def test_above_50_the_cap_is_20_percent():
    pvp = D("100.00")                                                        # cost 80 -> 20 % exactly
    assert evaluate(D("80.00"), D("90.00"), pvp).flags == ()
    assert evaluate(D("79.99"), D("90.00"), pvp).flags == (ABOVE_CAP,)
    assert evaluate(D("55.00"), D("90.00"), pvp).flags == (ABOVE_CAP,)       # cost >= 50 so cap 20 %, margin 45 %, was 10 %
    assert evaluate(D("49.00"), D("70.00"), D("60.00")).cap == D("0.30")      # cost < 50: 30 % cap


def test_missing_or_invalid_pvp_makes_the_margin_unavailable_without_blocking():
    for pvp in (None, D("0"), D("-1")):
        e = evaluate(D("5"), D("4"), pvp)
        assert e.flags == (UNAVAILABLE,) and e.margin_after is None and not e.blocked


def test_tips_give_the_cost_for_15_and_for_the_cap():
    e = evaluate(D("8.00"), D("8.00"), D("10.00"))
    assert e.cost_at_minimum == D("8.5000") and e.cost_at_cap == D("7.0000")


def test_floats_are_refused():
    with pytest.raises(TypeError):
        evaluate(1.5, D("1"), D("2"))  # type: ignore[arg-type]
