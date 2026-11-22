"""T043: estimated values are labelled estimated and nothing but ERP movements is ever labelled observed (SC-002, FR-014)."""

from db.tables import forecast_explanations
from runs.runner import RunConfig, run_forecast
from sqlalchemy import select
from test_seed_isolation import CLOCK, activate_valid, dense_csv, export_with_new_variant
from tests_helpers import FakeSource, NullWriter


def mix(engine, sku):
    with engine.connect() as c:
        return c.execute(select(forecast_explanations.c.provenance_mix, forecast_explanations.c.dataset_version_id).where(forecast_explanations.c.sku == sku)).one()


def test_seed_days_are_estimated_and_the_dataset_version_is_recorded(engine, store, tmp_path):
    did = activate_valid(engine, store, dense_csv())
    run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    m, dataset = mix(engine, "EJ-9001")
    assert dataset == did and m["estimated"] > 0 and m["manual"] == 0
    assert m["observed"] == 20                                                  # only the 20 real ERP days are observed; the seed rows are not


def test_without_a_seed_nothing_is_estimated(engine, tmp_path):
    run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    m, dataset = mix(engine, "EJ-9001")
    assert m["estimated"] == 0 and m["observed"] == 20 and dataset is None


def test_a_series_that_is_not_from_the_erp_is_never_observed(engine, make_export, tmp_path):
    export = make_export(seed=3)
    for s in export["series"]:
        s["provenance"] = "estimated"                                           # as the series export labels locally loaded data
    run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    with engine.connect() as c:
        rows = c.execute(select(forecast_explanations.c.provenance_mix)).all()
    assert rows and all(r.provenance_mix["observed"] == 0 for r in rows)
