"""T082: unchanged inputs and parameters give an identical re-forecast; a changed parameter gives a new, identified run."""

from datetime import UTC, datetime

from db.tables import forecast_runs, forecast_values
from parameters import save_parameter
from runs.runner import run_forecast
from sqlalchemy import func, select
from tests_helpers import FakeSource, NullWriter

CLOCK = lambda: datetime(2026, 11, 9, 8, tzinfo=UTC)  # noqa: E731


def values(engine, run_id):
    with engine.connect() as c:
        return sorted((r.variant_id, r.horizon_days, r.mean, str(r.quantiles), r.policy_used) for r in c.execute(select(forecast_values).where(forecast_values.c.run_id == run_id)).all())


def test_unchanged_inputs_and_parameters_reuse_the_run_and_the_outputs_are_identical(engine, make_export, tmp_path):
    a = run_forecast(engine, FakeSource(make_export(seed=5)), NullWriter(tmp_path), clock=CLOCK)
    b = run_forecast(engine, FakeSource(make_export(seed=5)), NullWriter(tmp_path), clock=CLOCK)
    assert b.reused and b.run_id == a.run_id and values(engine, b.run_id) == values(engine, a.run_id)
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(forecast_runs)).scalar() == 1


def test_a_parameter_change_makes_a_new_run_that_records_the_revisions_it_used(engine, make_export, tmp_path):
    first = run_forecast(engine, FakeSource(make_export(seed=5)), NullWriter(tmp_path), clock=CLOCK)
    with engine.begin() as c:
        save_parameter(c, "backtest.min_history", 90, "buyer-1", today=CLOCK().date())
    second = run_forecast(engine, FakeSource(make_export(seed=5)), NullWriter(tmp_path), clock=CLOCK)
    assert not second.reused and second.run_id != first.run_id
    with engine.connect() as c:
        runs = {r.id: r for r in c.execute(select(forecast_runs)).all()}
    assert runs[first.run_id].parameter_version_ids is None and runs[second.run_id].parameter_version_ids == {"backtest.min_history": 1}
    assert runs[second.run_id].config["backtest"]["min_history"] == 90
    third = run_forecast(engine, FakeSource(make_export(seed=5)), NullWriter(tmp_path), clock=CLOCK)
    assert third.reused and third.run_id == second.run_id                      # same parameters again: identical, not duplicated
