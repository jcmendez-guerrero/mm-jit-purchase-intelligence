"""T059: eligibility flags and the conservative min/max fallback."""

from db.tables import forecast_values
from policies.estimators import BASELINE
from runs.eligibility import decide
from runs.runner import RunConfig, run_forecast
from sqlalchemy import select
from tests_helpers import FakeSource, NullWriter


def seg(pattern="smooth", eligible=True, reasons=()):
    return {"pattern": pattern, "forecast_eligible": eligible, "reasons": list(reasons)}


def test_eligible_products_use_the_adopted_policy_for_their_pattern_else_the_baseline():
    assert decide(seg("intermittent"), {"intermittent": "tsb"}).policy == "tsb"
    assert decide(seg("smooth"), {"intermittent": "tsb"}).policy == BASELINE
    assert decide(seg(), {}).eligible is True


def test_ineligible_products_fall_back_to_conservative_min_max_with_the_reasons():
    d = decide(seg("new", False, ["new"]), {"new": "tsb"})
    assert (d.policy, d.eligible, d.reasons) == ("minmax_conservative", False, ("new",))
    multi = decide(seg("smooth", False, ["history_unreconciled", "pending_review"]), {})
    assert multi.reasons == ("history_unreconciled", "pending_review")
    assert decide(None, {}).reasons == ("not_classified",)


def test_no_point_forecast_is_published_for_an_ineligible_product(engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(make_export()), NullWriter(tmp_path))
    with engine.connect() as c:
        rows = c.execute(select(forecast_values)).all()
    inelig = [r for r in rows if not r.eligible]
    assert {r.variant_id for r in inelig} == {100, 101}
    assert all(r.mean is None and set(r.quantiles) == {"min", "max"} and r.policy_used == "minmax_conservative" for r in inelig)
    assert {r.reasons for r in inelig if r.variant_id == 100} == {"new"}
    assert all(r.eligible and r.mean is not None and "0.95" in r.quantiles for r in rows if r.variant_id <= 3)
    crit = [r for r in inelig if r.variant_id == 101]
    assert all(r.quantiles["max"] >= 1 for r in crit)           # clinically critical keeps cover although not forecastable


def test_horizons_are_stored_per_variant(engine, make_export, tmp_path):
    cfg = RunConfig(horizons=(7, 14))
    run_forecast(engine, FakeSource(make_export()), NullWriter(tmp_path), cfg)
    with engine.connect() as c:
        assert {r.horizon_days for r in c.execute(select(forecast_values)).all()} == {7, 14}
