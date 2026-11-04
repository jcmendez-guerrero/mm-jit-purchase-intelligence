"""Policy ladder, distributions and the conservative fallback."""

import math

import pytest
from policies.base import build_plan, prepare_history
from policies.dist import quantile
from policies.estimators import ADIDA, TSB, CrostonSBA, MinMaxPoisson, MovingAverage, SeasonalNaive
from policies.fallback import conservative_plan


def test_poisson_quantiles_match_known_values():
    assert quantile(2.0, 2.0, 0.95) == 5            # P(<=4)=0.947, P(<=5)=0.983
    assert quantile(0.2, 0.2, 0.85) == 1
    assert quantile(0.0, 0.0, 0.99) == 0


def test_overdispersed_demand_needs_more_stock_than_poisson():
    assert quantile(2.0, 6.0, 0.95) > quantile(2.0, 2.0, 0.95)


def test_quantiles_are_monotonic_in_the_level_and_validate_input():
    qs = [quantile(3.0, 5.0, lv) for lv in (0.5, 0.8, 0.9, 0.95, 0.99)]
    assert qs == sorted(qs)
    with pytest.raises(ValueError):
        quantile(1.0, 1.0, 1.0)


def test_prepare_history_drops_censored_days_and_clips_net_returns():
    assert prepare_history([3, -1, 0, 5], [False, False, True, False]) == [3, 0, 5]


def test_minmax_is_the_long_run_mean():
    assert MinMaxPoisson().rate([0, 0, 4, 0]) == 1.0 and MinMaxPoisson().rate([]) is None


def test_moving_average_and_seasonal_naive_need_enough_history():
    assert MovingAverage().rate([1] * 55) is None and MovingAverage().rate([1] * 56) == 1.0
    assert SeasonalNaive().rate([1] * 300) is None
    assert SeasonalNaive().rate([2] * 400) == 2.0


def test_croston_sba_on_regular_intermittent_demand():
    history = ([0, 0, 0, 2] * 30)
    assert CrostonSBA().rate(history) == pytest.approx(0.95 * 2 / 4, rel=1e-6)
    assert CrostonSBA().rate([0, 0, 0]) == 0.0 and CrostonSBA().rate([]) is None


def test_tsb_decays_for_a_dying_item_where_croston_does_not():
    dying = ([0, 0, 0, 2] * 25) + [0] * 200
    assert TSB().rate(dying) < 0.5 * CrostonSBA().rate(dying)


def test_adida_aggregates_weekly():
    assert ADIDA().rate([1] * 70) == pytest.approx(1.0, abs=1e-9)
    assert ADIDA().rate([1] * 20) is None


def test_plan_is_monotonic_in_service_level_and_includes_the_target_quantile():
    history = ([0, 0, 1, 0, 3, 0, 0] * 20)
    low = build_plan("x", 0.6, history, 14, 7, 0.85)
    high = build_plan("x", 0.6, history, 14, 7, 0.99)
    assert high.order_up_to >= low.order_up_to and high.reorder_point >= low.reorder_point
    assert low.safety_stock == max(0, low.order_up_to - math.ceil(low.mean_horizon)) and low.order_up_to >= low.reorder_point
    assert "0.85" in low.quantiles and "0.99" in high.quantiles


def test_overdispersion_in_history_raises_the_order_up_to_level():
    steady = [1] * 140
    bursty = ([0] * 20 + [30]) * 8                      # same mean rate as ~1.4/day, but delivered in rare bursts
    assert build_plan("x", 1.4, bursty, 14, 7, 0.95).order_up_to > build_plan("x", 1.4, steady, 14, 7, 0.95).order_up_to


def test_conservative_fallback_is_never_below_the_baseline_and_critical_keeps_one_unit():
    history = [0] * 150 + [1, 0, 0, 1, 0, 1, 0, 1]
    base = build_plan("b", MinMaxPoisson().rate(history) or 0, history, 14, 7, 0.95)
    fb = conservative_plan(history, 14, 7, 0.95).plan
    assert fb.order_up_to >= base.order_up_to and fb.policy == "minmax_conservative"
    rare = [0] * 300 + [1]
    assert conservative_plan(rare, 14, 7, 0.85, clinical_critical=True).plan.order_up_to >= 1
    assert conservative_plan([0] * 100, 14, 7, 0.85, clinical_critical=True).plan.order_up_to == 0   # never sold: nothing invented
