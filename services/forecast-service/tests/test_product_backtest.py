"""T049: per-product backtest on synthetic history with known error and bias, against the baseline (feature 012, FR-016, FR-018)."""

from decimal import Decimal

import pytest
from backtest.product import backtest_product
from backtest.runner import BacktestConfig
from conftest import Fixed
from policies.estimators import BASELINE, POLICIES

CFG = BacktestConfig()          # horizon 14, 12 origins every 7 days, at least 56 days of history


def series(demand, censored=None, level=0.95):
    return {"demand": list(demand), "censored": list(censored) if censored is not None else [False] * len(demand), "service_level": str(level)}


@pytest.fixture
def fixed(monkeypatch):
    def make(name, rate):
        monkeypatch.setitem(POLICIES, name, Fixed(name, rate))
        return name

    return make


def test_the_baseline_against_itself_is_a_tie_and_beats_the_baseline_by_definition():
    r = backtest_product(series([2] * 200), BASELINE, CFG)
    assert r.periods == 12 and r.wape == r.baseline_wape and r.bias == r.baseline_bias and r.beats_baseline is True


def test_a_method_that_over_forecasts_has_known_error_and_bias_and_loses_to_the_baseline(fixed):
    name = fixed("fixed_high", 3.0)                     # 3 a day against 2 a day sold: 42 forecast against 28 sold per 14 days
    r = backtest_product(series([2] * 200), name, CFG)
    assert r.periods == 12
    assert r.wape == Decimal("0.500000") and r.bias == Decimal("0.500000")
    assert r.baseline_wape == Decimal("0.000000") and r.beats_baseline is False


def test_a_method_that_beats_the_baseline_is_not_flagged(fixed):
    demand = [4] * 100 + [1] * 100                       # the level drops: the baseline lags behind, a method that follows the new level wins
    name = fixed("fixed_exact", 1.0)
    r = backtest_product(series(demand), name, BacktestConfig(origins=4, step=7))
    assert r.periods == 4 and r.wape < r.baseline_wape and r.beats_baseline is True


def test_windows_dominated_by_stockouts_are_not_scored():
    demand = [2] * 200
    censored = [False] * 130 + [True] * 70               # the last windows are almost all stockout days
    r = backtest_product(series(demand, censored), BASELINE, CFG)
    assert 0 < r.periods < 12


def test_a_short_history_has_no_windows_and_is_not_flagged():
    r = backtest_product(series([2] * 30), BASELINE, CFG)
    assert (r.periods, r.wape, r.bias, r.baseline_wape) == (0, None, None, None) and r.beats_baseline is True


def test_a_product_with_no_sales_in_the_windows_has_no_error_to_report():
    r = backtest_product(series([0] * 200), BASELINE, CFG)
    assert r.wape is None and r.bias is None and r.beats_baseline is True


def test_a_method_that_cannot_run_falls_back_to_the_baseline_for_that_window():
    class Never:
        name, version = "never", "t"

        def rate(self, history):
            return None

    POLICIES["never"] = Never()
    try:
        r = backtest_product(series([2] * 200), "never", CFG)
    finally:
        del POLICIES["never"]
    assert r.periods == 12 and r.wape == r.baseline_wape


def test_the_same_input_gives_the_same_result():
    s = series([(i * 7) % 5 for i in range(200)])
    assert backtest_product(s, BASELINE, CFG) == backtest_product(s, BASELINE, CFG)
