"""MMI-7 T032 (US3 scenario 3): a forecast produced while a dataset was active keeps showing which dataset version it used, after a rollback and later runs."""

from db.tables import forecast_runs, forecast_values
from runs.runner import RunConfig, run_forecast
from seeds.lifecycle import rollback
from sqlalchemy import select
from test_seed_isolation import CLOCK, activate_valid, dense_csv, export_with_new_variant
from tests_helpers import FakeSource, NullWriter


def test_a_seeded_run_keeps_its_dataset_version_after_the_rollback_and_a_later_run(engine, store, tmp_path):
    did = activate_valid(engine, store, dense_csv())
    seeded_run = run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    with engine.begin() as c:
        rollback(c, store, "admin-1", reason_code="wrong_figures")
    later = run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    assert later.run_id != seeded_run.run_id                                      # the rollback produced a different run, not an edit of the old one
    with engine.connect() as c:
        old = c.execute(select(forecast_runs).where(forecast_runs.c.id == seeded_run.run_id)).one()
        new = c.execute(select(forecast_runs).where(forecast_runs.c.id == later.run_id)).one()
        old_rows = c.execute(select(forecast_values).where(forecast_values.c.run_id == seeded_run.run_id)).all()
    assert old.dataset_version_id == did and old.config["seed"]["dataset_id"] == did          # still explains itself
    assert old_rows and all(r.reasons == "seed_used" for r in old_rows)
    assert new.dataset_version_id is None and "seed" not in new.config
