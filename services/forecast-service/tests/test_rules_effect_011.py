"""Feature 011 (T036, T037, T061): the rules a person changes in the console change the next forecast, and each run records which versions it used."""

import copy

from db.tables import forecast_runs, forecast_values
from parameters import save_parameter
from runs.runner import run_forecast
from sqlalchemy import select
from tests_helpers import FakeSource, NullWriter

SPIKE_AT = -5                    # a day near the end of the history, so it weighs on the estimate


def with_spike(export, censored):
    """The first smooth series with one very large day; `censored` says whether the inventory service marked that day as not observable (an exclusion or a censoring rule)."""
    doc = copy.deepcopy(export)
    s = doc["series"][0]
    s["demand"][SPIKE_AT] = 900
    s["censored"][SPIKE_AT] = censored
    return doc


def mean_of(engine, run_id, variant_id=1, horizon=7):
    with engine.connect() as c:
        return c.execute(select(forecast_values.c.mean).where(forecast_values.c.run_id == run_id, forecast_values.c.variant_id == variant_id,
                                                              forecast_values.c.horizon_days == horizon)).scalar_one()


def test_days_the_inventory_service_marks_as_not_observable_stop_weighing_on_the_forecast(engine, make_export, tmp_path):
    """An exclusion of a promotion, or a censoring rule that treats a stock-out as hidden demand, reaches the forecast as censored days."""
    base = make_export()
    counted = run_forecast(engine, FakeSource(with_spike(base, False)), NullWriter(tmp_path))
    excluded_doc = {**with_spike(base, True), "rule_versions": {"exclusions": 1, "censoring.min_zero_stock_days": 0}}
    excluded = run_forecast(engine, FakeSource(excluded_doc), NullWriter(tmp_path))
    assert excluded.run_id != counted.run_id and not excluded.reused                              # changed inputs make a new run
    assert mean_of(engine, excluded.run_id) < mean_of(engine, counted.run_id)                      # the promotion no longer inflates the estimate
    with engine.connect() as c:
        run = c.execute(select(forecast_runs).where(forecast_runs.c.id == excluded.run_id)).one()
    assert run.rule_version_ids == {"exclusions": 1, "censoring.min_zero_stock_days": 0}


def test_reversing_the_exclusion_brings_the_forecast_back(engine, make_export, tmp_path):
    base = make_export()
    counted = run_forecast(engine, FakeSource(with_spike(base, False)), NullWriter(tmp_path))
    run_forecast(engine, FakeSource(with_spike(base, True)), NullWriter(tmp_path))
    again = run_forecast(engine, FakeSource(with_spike(base, False)), NullWriter(tmp_path))
    assert again.reused and again.run_id == counted.run_id                                        # the same inputs give the identical run again


def test_a_saved_forecast_parameter_makes_a_new_run_with_other_quantiles_and_records_its_version(engine, make_export, tmp_path):
    export = make_export()
    first = run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    with engine.begin() as c:
        assert save_parameter(c, "lead_time", 28, "buyer-1") == 1
    second = run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    assert second.run_id != first.run_id and not second.reused
    with engine.connect() as c:
        run = c.execute(select(forecast_runs).where(forecast_runs.c.id == second.run_id)).one()
        q = lambda rid: c.execute(select(forecast_values.c.quantiles).where(forecast_values.c.run_id == rid, forecast_values.c.variant_id == 101,       # noqa: E731
                                                                            forecast_values.c.horizon_days == 28)).scalar_one()
        assert run.parameter_version_ids == {"lead_time": 1} and run.config["lead_time"] == 28
        # variant 101 has no reliable forecast, so its reorder point (the "min") is the conservative one over the lead time: the parameter moves it
        assert q(second.run_id)["min"] > q(first.run_id)["min"]
