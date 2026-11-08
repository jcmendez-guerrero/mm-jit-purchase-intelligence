"""T181 (edge case: overlap with actual ERP periods, FR-025): actuals prevail and the overlap is reported."""

from datetime import date
from decimal import Decimal

from backtest.runner import BacktestConfig
from conftest import KNOWN, export_series
from db.tables import forecast_runs
from runs.runner import RunConfig, run_forecast
from runs.seeds import apply_seeds
from seeds.dryrun import dry_run
from seeds.lifecycle import register_upload, validate_dataset
from sqlalchemy import select
from test_seed_isolation import CLOCK, activate_valid, dense_csv, seeded, short_series
from tests_helpers import FakeSource, NullWriter
from upload_settings import ParseLimits

D = Decimal
MIN = 56


def test_seed_days_that_fall_on_actual_days_are_counted_per_variant_and_day():
    s = short_series(9001, 20, "2026-03-01")                        # actual days 2026-03-01 .. 2026-03-20
    seeds = seeded(9001, 30, date(2026, 2, 20))                     # seed days 2026-02-20 .. 2026-03-21: nine before, twenty on actual days, one after
    out, rep = apply_seeds([s], seeds, MIN)
    assert (rep.overlap_variants, rep.overlap_days) == (1, 20)
    assert out[0]["demand"][-20:] == s["demand"]                      # the actual days are untouched


def test_seeds_entirely_before_the_actuals_do_not_overlap():
    _out, rep = apply_seeds([short_series(9001, 20, "2026-03-01")], seeded(9001, 10, date(2026, 2, 1)), MIN)
    assert (rep.overlap_variants, rep.overlap_days) == (0, 0)


def test_a_variant_with_enough_history_still_reports_the_overlap_though_its_seeds_are_not_used():
    long = export_series(9001, [2] * 90, "smooth", True)
    long["start_day"] = "2026-01-01"
    _out, rep = apply_seeds([long], seeded(9001, 30, date(2026, 1, 10)), MIN)
    assert (rep.overlap_variants, rep.overlap_days, rep.used) == (1, 30, set())


def test_the_dry_run_and_the_run_report_the_overlap(engine, store, tmp_path):
    did = activate_valid(engine, store, dense_csv(9001, date(2026, 1, 1), 90))          # 2026-01-01 .. 2026-03-31: 59 days before the actuals, 20 on them, 11 after
    series = [short_series(9001, 20, "2026-03-01")]                                      # actuals 2026-03-01 .. 2026-03-20
    with engine.begin() as c:
        up = register_upload(c, store, "otro.csv", dense_csv(9001, date(2026, 1, 1), 90).replace(b"Hoja", b"Otra"), "Otra", "buyer-1", ParseLimits())
        validate_dataset(c, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-1", ParseLimits())
        out = dry_run(c, up["id"], series, BacktestConfig())
    assert out["overlap"] == {"variants": 1, "days": 20}
    run = run_forecast(engine, FakeSource({"through_day": "2026-10-31", "series": series}), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    with engine.connect() as c:
        cfg = c.execute(select(forecast_runs.c.config).where(forecast_runs.c.id == run.run_id)).scalar_one()
    assert cfg["seed"] == {"dataset_id": did, "variants_used": 1, "overlap_variants": 1, "overlap_days": 20}
