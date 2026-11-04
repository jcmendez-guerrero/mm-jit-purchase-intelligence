"""T060: rolling-origin backtest scoring by stockout/holding/expiry cost, and the adoption rule."""

import random
from decimal import Decimal

from backtest.runner import BacktestConfig, BacktestSeries, Cost, backtest_series, compare, select_policies
from conftest import Fixed, weekly_series
from policies.estimators import MinMaxPoisson, MovingAverage


def series(demand, vid=1, price="10", segment="smooth", level=0.95, censored=None):
    return BacktestSeries(vid, demand, censored or [False] * len(demand), Decimal(price), segment, level)


CFG = BacktestConfig(horizon=14, lead_time=7, origins=8, step=7, min_history=56)


def test_underforecasting_costs_stockouts_and_overforecasting_costs_holding_and_expiry():
    demand = [1] * 200
    under = backtest_series(series(demand), Fixed("zero", 0.0), CFG)
    over = backtest_series(series(demand), Fixed("huge", 20.0), CFG)
    assert under.stockout > 0 and under.holding == 0 and under.expiry == 0
    assert over.holding > 0 and over.expiry > 0 and over.stockout == 0
    assert under.windows == over.windows == 8


def test_costs_scale_with_price_and_use_decimal():
    a = backtest_series(series([1] * 200, price="10"), Fixed("zero", 0.0), CFG)
    b = backtest_series(series([1] * 200, price="20"), Fixed("zero", 0.0), CFG)
    assert b.stockout == 2 * a.stockout and isinstance(a.total, Decimal)


def test_the_policy_only_sees_history_before_each_origin():
    seen = []

    class Spy:
        name, version = "spy", "t"

        def rate(self, history):
            seen.append(len(history))
            return 1.0

    backtest_series(series([1] * 100), Spy(), BacktestConfig(horizon=14, origins=3, step=7, min_history=10))
    assert seen == [100 - 14 - 14, 100 - 14 - 7, 100 - 14]  # never the future


def test_windows_dominated_by_stockouts_are_skipped_and_censored_days_are_dropped_from_history():
    demand = [1] * 100
    censored = [False] * 70 + [True] * 30
    c = backtest_series(series(demand, censored=censored), Fixed("x", 1.0), BacktestConfig(horizon=14, origins=4, step=7, min_history=10))
    assert c.windows < 4


def test_short_histories_produce_no_windows():
    assert backtest_series(series([1] * 30), Fixed("x", 1.0), CFG).windows == 0


def shifted(seed, n=10):
    rng = random.Random(seed)  # noqa: S311 - deterministic test data
    return [series(weekly_series(rng, 40, 3, shift_after=26, shift_factor=3.0), vid=i) for i in range(n)]


def test_a_better_method_is_adopted_only_where_it_measurably_wins():
    results = compare(shifted(7), [MinMaxPoisson(), MovingAverage()], BacktestConfig(origins=12, step=7))
    per = results["smooth"]
    assert per["moving_average"].total < per["minmax_poisson"].total      # recent level shift: long-run mean is slow
    assert select_policies(results, BacktestConfig(origins=12, step=7))["smooth"] == "moving_average"


def test_baseline_stays_when_the_gain_is_below_the_margin_or_windows_are_too_few():
    results = {"smooth": {"minmax_poisson": Cost(Decimal(100), Decimal(0), Decimal(0), 40), "tsb": Cost(Decimal(97), Decimal(0), Decimal(0), 40)}}
    assert select_policies(results, BacktestConfig())["smooth"] == "minmax_poisson"                       # 3 % < 5 % margin
    results["smooth"]["tsb"] = Cost(Decimal(50), Decimal(0), Decimal(0), 10)
    assert select_policies(results, BacktestConfig())["smooth"] == "minmax_poisson"                       # only 10 windows
    results["smooth"]["tsb"] = Cost(Decimal(50), Decimal(0), Decimal(0), 40)
    assert select_policies(results, BacktestConfig())["smooth"] == "tsb"


def test_selection_is_deterministic_on_ties():
    base = Cost(Decimal(100), Decimal(0), Decimal(0), 40)
    tie = Cost(Decimal(10), Decimal(0), Decimal(0), 40)
    r = {"s": {"minmax_poisson": base, "b_policy": tie, "a_policy": tie}}
    assert select_policies(r, BacktestConfig())["s"] == "a_policy"
