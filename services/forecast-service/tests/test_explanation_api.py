"""T031, T032: the explanation endpoint - SKU only, versions present, no forecast figure when not eligible, and error codes."""

import api
import pytest
from fastapi.testclient import TestClient
from mmi_common.service import create_service_app
from runs.runner import run_forecast
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


def test_without_any_run_the_explanation_is_not_available_with_a_code(client):
    r = client.get("/forecasts/products/EJ-1/explanation", headers=H)
    assert r.status_code == 404 and r.json()["detail"] == "forecast_explanation_not_available"


def test_an_eligible_product_shows_versions_class_method_and_the_expected_figure(client, engine, make_export, tmp_path):
    res = run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    body = client.get("/forecasts/products/EJ-1/explanation", headers=H).json()
    assert body["sku"] == "EJ-1" and body["run_id"] == res.run_id and body["eligibility"] == "eligible"
    assert body["model_version"] and "@" in body["model_version"] and body["method"] and body["method_reason_code"]
    assert (body["abc"], body["xyz"], body["pattern"]) == ("B", "Y", "smooth") and body["expected"] is not None and body["history_start"] == "2026-01-01"
    assert "variant_id" not in body and "run_id" in body                      # users see the SKU; the ERP id never leaves the service


def test_a_not_eligible_product_has_no_forecast_figure_and_its_reasons(client, engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    body = client.get("/forecasts/products/EJ-100/explanation", headers=H).json()
    assert body["eligibility"] == "not_eligible" and body["eligibility_reason_codes"] == ["new"]
    assert (body["low"], body["expected"], body["high"], body["confidence"]) == (None, None, None, None)
    assert body["method_reason_code"] == "min_max_fallback"


def test_an_older_run_can_be_asked_for_by_id_and_keeps_its_own_explanation(client, engine, make_export, tmp_path):
    first = run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    first_body = client.get("/forecasts/products/EJ-1/explanation", headers=H).json()
    second = run_forecast(engine, FakeSource(make_export(seed=4)), NullWriter(tmp_path))
    latest = client.get("/forecasts/products/EJ-1/explanation", headers=H).json()
    old = client.get(f"/forecasts/products/EJ-1/explanation?run_id={first.run_id}", headers=H).json()
    assert latest["run_id"] == second.run_id and old == first_body and old["run_id"] == first.run_id


def test_unknown_sku_run_and_missing_token_use_codes(client, engine, make_export, tmp_path):
    run_forecast(engine, FakeSource(make_export(seed=3)), NullWriter(tmp_path))
    assert client.get("/forecasts/products/NOPE/explanation", headers=H).json()["detail"] == "forecast_explanation_not_available"
    assert client.get("/forecasts/products/EJ-1/explanation?run_id=missing", headers=H).json()["detail"] == "forecast_explanation_not_available"
    assert client.get("/forecasts/products/EJ-1/explanation").status_code == 401
