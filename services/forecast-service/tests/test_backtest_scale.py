"""T052: a full-catalogue backtest of 5,000 synthetic products finishes well inside the 15 minutes allowed (SC-006)."""

import time

from backtest.product import backtest_product
from backtest.runner import BacktestConfig
from policies.estimators import BASELINE


def test_five_thousand_products_are_backtested_quickly():
    cfg = BacktestConfig()
    started = time.monotonic()
    done = 0
    for i in range(5000):
        demand = [(i + d * 3) % 5 for d in range(150)]
        r = backtest_product({"demand": demand, "censored": [False] * 150, "service_level": "0.95"}, BASELINE, cfg)
        done += r.periods > 0
    elapsed = time.monotonic() - started
    assert done == 5000 and elapsed < 300, f"{elapsed:.0f}s for 5000 products"
