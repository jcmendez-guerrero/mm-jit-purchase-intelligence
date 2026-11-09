"""T167 (FR-023): the dry-run shows a backtest comparison before activation, stores nothing and changes no ERP-derived data."""

import random
from decimal import Decimal

from backtest.runner import BacktestConfig
from conftest import KNOWN, SKUS, export_series
from db.tables import forecast_runs, forecast_values, seed_datasets
from seeds.dryrun import dry_run
from seeds.lifecycle import register_upload, validate_dataset
from sqlalchemy import func, select
from test_seed_isolation import dense_csv, short_series
from upload_settings import ParseLimits

L = ParseLimits()


def long_series(variant, n=200):
    rng = random.Random(variant)  # noqa: S311 - deterministic test data
    return export_series(variant, [max(0, int(rng.gauss(4, 1.5))) for _ in range(n)], "smooth", True)


def candidate(engine, store, data):
    with engine.begin() as c:
        up = register_upload(c, store, "d.csv", data, "x", "buyer-1", L)
        validate_dataset(c, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-1", L, sku_map=SKUS)
        return up["id"]


def test_the_comparison_adds_the_rescued_variant_to_the_backtest(engine, store):
    did = candidate(engine, store, dense_csv(9001))
    series = [long_series(9002), short_series(9001, 20, "2026-03-01")]
    with engine.begin() as c:
        out = dry_run(c, did, series, BacktestConfig())
    bt = out["backtest"]
    assert bt["status"] == "ok" and bt["basis"] == "actual_demand_only"
    assert bt["before"]["variants"] == 1 and bt["after"]["variants"] == 2             # the seeded new variant now takes part
    assert bt["after"]["windows"] > bt["before"]["windows"]
    assert Decimal(bt["delta_cost"]) == Decimal(bt["after"]["cost"]) - Decimal(bt["before"]["cost"])


def test_without_enough_forecastable_history_the_comparison_says_so(engine, store):
    did = candidate(engine, store, dense_csv(9001))
    with engine.begin() as c:
        out = dry_run(c, did, [short_series(9003, 10, "2026-03-01")], 56)
    assert out["backtest"]["status"] == "insufficient_history" and out["backtest"]["delta_cost"] is None


def test_a_dry_run_stores_nothing_and_never_activates(engine, store):
    did = candidate(engine, store, dense_csv(9001))
    with engine.begin() as c:
        dry_run(c, did, [long_series(9002), short_series(9001, 20, "2026-03-01")], 56)
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(forecast_runs)).scalar_one() == 0
        assert c.execute(select(func.count()).select_from(forecast_values)).scalar_one() == 0
        assert c.execute(select(seed_datasets.c.status).where(seed_datasets.c.id == did)).scalar_one() != "active"
