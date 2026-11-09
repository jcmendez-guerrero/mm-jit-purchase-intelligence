"""T172 (SC-002): a 1,000-product file goes from upload to activation in under 15 minutes and rolls back in under 2 minutes.

Synthetic data only: 1,000 products of 50 days each, identified by SKU (50,000 rows: exactly the hard row cap, SC-006). The budgets are the success criterion; the
test measures the service-level journey (upload, validation, dry-run comparison, activation, rollback) on the unit-test database.
"""

import random
import time
from datetime import date, timedelta

import seed_fixtures as sf
from backtest.runner import BacktestConfig
from conftest import export_series
from seeds.dryrun import dry_run
from seeds.lifecycle import activate, register_upload, rollback, validate_dataset
from upload_settings import ParseLimits

PRODUCTS, DAYS = 1000, 50
VALIDATION_BUDGET_S = 5 * 60
UPLOAD_TO_ACTIVATION_BUDGET_S = 15 * 60
ROLLBACK_BUDGET_S = 2 * 60
L = ParseLimits()


def big_csv() -> bytes:
    head = ";".join(["SKU", *sf.HEADER[1:]])
    start = date(2026, 1, 1)
    rows = [f"EJ-{v};{(start + timedelta(days=d)).isoformat()};{(v + d) % 5 + 1};;estimado;Hoja sintética A;sintético" for v in range(1, PRODUCTS + 1) for d in range(DAYS)]
    return ("\n".join([head, *rows]) + "\n").encode()


def series():
    rng = random.Random(7)  # noqa: S311 - deterministic test data
    return [export_series(v, [max(0, int(rng.gauss(3, 1))) for _ in range(120)], "smooth", True) for v in range(1, PRODUCTS + 1)]


def test_a_thousand_products_reach_activation_within_budget_and_roll_back_within_budget(engine, store):
    data = big_csv()
    assert len(data) < L.max_bytes
    known = set(range(1, PRODUCTS + 1))
    started = time.perf_counter()
    with engine.begin() as c:
        up = register_upload(c, store, "mil-productos.csv", data, "Mil productos", "buyer-1", L)
        validating = time.perf_counter()
        res = validate_dataset(c, store, up["id"], up["suggested_mapping"], known, "buyer-1", L, sku_map={f"EJ-{v}": v for v in known})
        validated_in = time.perf_counter() - validating
        assert res["accepted"] == PRODUCTS * DAYS == L.max_rows and res["quarantined"] == 0
        assert validated_in < VALIDATION_BUDGET_S, f"{validated_in:.0f}s"
        dry = dry_run(c, up["id"], series(), BacktestConfig())
        assert dry["backtest"]["status"] in ("ok", "insufficient_history")
        activate(c, store, up["id"], "approver-9")
    to_activation = time.perf_counter() - started
    assert to_activation < UPLOAD_TO_ACTIVATION_BUDGET_S, f"{to_activation:.0f}s"

    rb_started = time.perf_counter()
    with engine.begin() as c:
        rollback(c, store, "buyer-1", reason_code="test")
    rolled_back = time.perf_counter() - rb_started
    assert rolled_back < ROLLBACK_BUDGET_S, f"{rolled_back:.0f}s"
    print(f"TIMING validation={validated_in:.1f}s upload_to_activation={to_activation:.1f}s rollback={rolled_back:.1f}s")
