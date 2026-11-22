"""T052, T092: a full-catalogue backtest of 5,000 synthetic products finishes inside the 20 seconds a request may take (SC-006, FR-022).

Past that limit the job has to move to the background (T025, T055); this test is the signal that tells us so.
"""

import time

from backtest.jobs import run_backtest
from backtest.product import backtest_product
from backtest.runner import BacktestConfig
from policies.estimators import CANDIDATES
from tests_helpers import FakeSource

LIMIT_SECONDS = 20
METHODS = [p.name for p in CANDIDATES]


def _series(i):
    return {"demand": [(i + d * 3) % 5 for d in range(150)], "censored": [False] * 150, "service_level": "0.95"}


def test_five_thousand_products_are_backtested_with_every_method_inside_the_limit():
    cfg = BacktestConfig()
    started = time.monotonic()
    done = sum(backtest_product(_series(i), METHODS[i % len(METHODS)], cfg).periods > 0 for i in range(5000))
    elapsed = time.monotonic() - started
    assert done == 5000 and elapsed < LIMIT_SECONDS, f"{elapsed:.0f}s for 5000 products"


def test_the_whole_catalogue_job_with_its_database_writes_stays_inside_the_limit(engine):
    series = [{"variant_id": i, "sku": f"SYN-{i:05d}", **_series(i)} for i in range(1, 5001)]
    started = time.monotonic()
    out = run_backtest(engine, FakeSource({"through_day": "2026-11-01", "series": series}), scope="catalogue", sku=None, actor="buyer-1")
    elapsed = time.monotonic() - started
    assert out["status"] == "completed" and out["products"] == 5000 and elapsed < LIMIT_SECONDS, f"{elapsed:.0f}s for the whole job"
