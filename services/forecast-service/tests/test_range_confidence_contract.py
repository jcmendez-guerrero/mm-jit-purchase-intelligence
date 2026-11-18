"""T042: every eligible forecast carries a range in order, a confidence label and its versions; a low-confidence product carries none and is published as min/max (SC-001)."""

import random

import api
import pytest
from conftest import export_series, weekly_series
from db.tables import forecast_explanations, forecast_runs, forecast_values
from fastapi.testclient import TestClient
from mmi_common.service import create_service_app
from runs.runner import run_forecast
from sqlalchemy import select
from tests_helpers import FakeSource, NullWriter

H = {"Authorization": "Bearer x"}


class _V:
    def validate(self, token, required_roles=()):
        from mmi_common.auth import Principal

        return Principal("svc", frozenset({"viewer"}), None)


@pytest.fixture
def client(engine):
    app = create_service_app("forecast-service", validator=_V())
    app.include_router(api.build_router(app))
    app.dependency_overrides[api.get_engine] = lambda: engine
    return TestClient(app)


def export_with_low_confidence(make_export):
    export = make_export(seed=3)
    rng = random.Random(7)  # noqa: S311 - deterministic test data
    s = export_series(200, weekly_series(rng, 9, 0.4), "intermittent", True)           # 63 days, mostly zeros ...
    s["segment"]["xyz"] = "Z"                                                            # ... and very variable: three flags
    s["censored"] = [False] * 40 + [True] * 23                                           # ... and a long stockout
    export["series"].append(s)
    return export


def explanations(engine):
    with engine.connect() as c:
        return {r.sku: r for r in c.execute(select(forecast_explanations)).all()}


def test_every_eligible_forecast_has_an_ordered_range_a_confidence_label_and_versions(engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    rows = explanations(engine)
    eligible = [r for r in rows.values() if r.eligibility == "eligible"]
    assert len(eligible) == 3
    for r in eligible:
        assert r.low is not None and r.high is not None and 0 <= r.low <= r.expected <= r.high
        assert r.confidence in ("alta", "media") and r.model_version
        assert isinstance(r.confidence_reason_codes, list)


def test_a_not_eligible_product_has_no_range_and_no_confidence(engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    r = explanations(engine)["EJ-100"]
    assert (r.low, r.expected, r.high, r.confidence) == (None, None, None, None)


def test_a_low_confidence_product_is_manual_review_only_with_no_figure_and_published_as_min_max(engine, make_export, tmp_path):
    res = run_forecast(engine, FakeSource(export_with_low_confidence(make_export)), NullWriter(tmp_path))
    r = explanations(engine)["EJ-200"]
    assert (r.eligibility, r.confidence) == ("manual_review_only", "baja")
    assert (r.low, r.expected, r.high) == (None, None, None)
    assert r.eligibility_reason_codes[0] == "low_confidence" and {"short_history", "high_variability", "many_stockout_days"} <= set(r.confidence_reason_codes)
    with engine.connect() as c:
        vals = c.execute(select(forecast_values).where(forecast_values.c.run_id == res.run_id, forecast_values.c.variant_id == 200)).all()
        run = c.execute(select(forecast_runs)).one()
    assert vals and all((not v.eligible) and v.mean is None and v.reasons == "low_confidence" and v.policy_used == "minmax_conservative" for v in vals)
    assert run.eligible_count == 3 == res.eligible                                       # the low-confidence product is not counted as forecast-eligible


def test_the_endpoint_returns_the_range_as_decimal_strings_and_the_label(client, engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    body = client.get("/forecasts/products/EJ-1/explanation", headers=H).json()
    assert body["confidence"] in ("alta", "media") and float(body["low"]) <= float(body["expected"]) <= float(body["high"])
    assert all(len(body[k].split(".")[1]) == 4 for k in ("low", "expected", "high"))


def test_the_endpoint_shows_the_low_confidence_label_and_reasons_without_a_figure(client, engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(export_with_low_confidence(make_export)), NullWriter(tmp_path))
    body = client.get("/forecasts/products/EJ-200/explanation", headers=H).json()
    assert body["eligibility"] == "manual_review_only" and body["confidence"] == "baja" and body["expected"] is None and body["low"] is None
