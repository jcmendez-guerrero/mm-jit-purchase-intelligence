"""T102 + T113: seeds extend short histories only, actuals prevail, runs record the dataset, and seeds never touch ERP-derived data."""

from datetime import UTC, date, datetime, timedelta

import seed_fixtures as sf
from conftest import KNOWN, export_series
from db.tables import forecast_runs, forecast_values, seed_rows
from runs.runner import RunConfig, run_forecast
from runs.seeds import ActiveSeeds, apply_seeds, load_active
from seeds.lifecycle import activate, register_upload, rollback, validate_dataset
from sqlalchemy import select
from tests_helpers import FakeSource, NullWriter
from upload_settings import ParseLimits

D = __import__("decimal").Decimal
CLOCK = lambda: datetime(2026, 11, 9, 8, tzinfo=UTC)  # noqa: E731
MIN = 56


def seeded(variant, days, start, qty=3):
    return ActiveSeeds("ds-1", 1, {variant: {start + timedelta(days=i): D(qty) for i in range(days)}})


def short_series(variant=9001, n=20, start="2026-03-01", eligible=False, reasons=("new",)):
    s = export_series(variant, [1] * n, "new" if not eligible else "smooth", eligible, list(reasons))
    s["start_day"] = start
    return s


def test_dense_seeds_extend_a_short_history_and_rescue_a_new_variant():
    out, rep = apply_seeds([short_series()], seeded(9001, 60, date(2026, 1, 1)), MIN)
    s = out[0]
    assert rep.used == {9001} and len(s["demand"]) == 20 + 59 and s["start_day"] == "2026-01-01" and s["demand"][:59] == [3] * 59 and s["segment"]["forecast_eligible"] is True
    assert len(s["censored"]) == len(s["demand"])


def test_actual_history_prevails_on_every_overlapping_day():
    seeds = ActiveSeeds("ds", 1, {9001: {date(2026, 1, 1) + timedelta(days=i): D(3) for i in range(90)}})      # seeds also cover March, where actuals exist
    out, _ = apply_seeds([short_series(start="2026-03-01")], seeds, MIN)
    assert out[0]["demand"][-20:] == [1] * 20 and len(out[0]["demand"]) == 59 + 20             # only days before the first actual day come from the seed


def test_a_variant_with_enough_actual_history_never_consults_the_seeds():
    full = export_series(9001, [2] * 80, "smooth", True)
    out, rep = apply_seeds([full], seeded(9001, 60, date(2025, 1, 1)), MIN)
    assert out == [full] and rep.used == set()


def test_sparse_seeds_are_skipped_and_reported_not_zero_filled():
    seeds = ActiveSeeds("ds", 1, {9001: {date(2026, 1, 1): D(5), date(2026, 2, 1): D(5)}})
    out, rep = apply_seeds([short_series()], seeds, MIN)
    assert out[0]["demand"] == [1] * 20 and rep.skipped_sparse == {9001} and rep.used == set()


def test_a_variant_that_is_not_forecastable_for_another_reason_is_left_alone():
    out, rep = apply_seeds([short_series(reasons=("too_sparse",))], seeded(9001, 60, date(2026, 1, 1)), MIN)
    assert rep.used == set() and len(out[0]["demand"]) == 20


def test_variants_without_seed_rows_are_untouched():
    s = short_series(variant=9002)
    assert apply_seeds([s], seeded(9001, 60, date(2026, 1, 1)), MIN)[0] == [s]


def activate_valid(engine, store, data):
    with engine.begin() as c:
        up = register_upload(c, store, "d.csv", data, "x", "buyer-1", ParseLimits())
        validate_dataset(c, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-1", ParseLimits())
        activate(c, store, up["id"], "buyer-1")
        return up["id"]


def dense_csv(variant=9001, start=date(2026, 1, 1), days=60):
    head = ";".join(sf.HEADER)
    rows = [f"{variant};{(start + timedelta(days=i)).isoformat()};2;;estimado;Hoja sintética A;sintético" for i in range(days)]
    return ("\n".join([head, *rows]) + "\n").encode()


def export_with_new_variant():
    return {"through_day": "2026-10-31", "count": 1, "series": [short_series(9001, 20, "2026-03-01")]}


def test_a_run_uses_the_active_dataset_records_it_and_flags_the_seeded_variant(engine, store, tmp_path):
    plain = run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    did = activate_valid(engine, store, dense_csv())
    seeded_run = run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    assert not seeded_run.reused and seeded_run.run_id != plain.run_id
    with engine.connect() as c:
        run = c.execute(select(forecast_runs).where(forecast_runs.c.id == seeded_run.run_id)).one()
        rows = c.execute(select(forecast_values).where(forecast_values.c.run_id == seeded_run.run_id)).all()
    assert run.dataset_version_id == did and rows and all(r.eligible and r.reasons == "seed_used" for r in rows)
    assert all(not r.eligible for r in _rows(engine, plain.run_id))                              # without the seed the variant stays on min/max


def _rows(engine, run_id):
    with engine.connect() as c:
        return c.execute(select(forecast_values).where(forecast_values.c.run_id == run_id)).all()


def test_rollback_makes_the_next_run_identical_to_the_one_before_the_activation(engine, store, tmp_path):
    before = run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    activate_valid(engine, store, dense_csv())
    with engine.begin() as c:
        rollback(c, store, "admin-1")
    after = run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    assert after.reused and after.run_id == before.run_id


def test_seeds_live_only_in_seed_tables_and_never_in_the_series_the_erp_exports(engine, store):
    activate_valid(engine, store, dense_csv())
    with engine.connect() as c:
        assert load_active(c).by_variant[9001][date(2026, 1, 1)] == D(2)
        assert c.execute(select(seed_rows.c.kind)).scalars().all()[0] == "estimated"
    series = export_with_new_variant()["series"]
    snapshot = [dict(s) for s in series]
    with engine.connect() as c:
        apply_seeds(series, load_active(c), MIN)
    assert series == snapshot                                                                    # the exported ERP series is not mutated
