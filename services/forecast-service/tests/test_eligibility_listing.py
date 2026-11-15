"""T060b (forecast side): the latest run's eligibility and confidence by SKU, for inventory-service's portfolio."""

import random

import api
import pytest
from conftest import export_series, weekly_series
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


def test_without_a_run_there_is_nothing_to_list(client):
    r = client.get("/forecasts/eligibility", headers=H)
    assert r.status_code == 404 and r.json()["detail"] == "no_forecast_run"


def test_every_product_of_the_latest_run_is_listed_by_sku_with_eligibility_and_confidence(client, engine, make_export, tmp_path):
    export = make_export(seed=3)
    s = export_series(200, weekly_series(random.Random(7), 9, 0.4), "intermittent", True)         # noqa: S311 - deterministic test data
    s["segment"]["xyz"] = "Z"
    s["censored"] = [False] * 40 + [True] * 23                                                    # three flags: low confidence
    export["series"].append(s)
    res = run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    body = client.get("/forecasts/eligibility", headers=H).json()
    by_sku = {v["sku"]: v for v in body["variants"]}
    assert body["run_id"] == res.run_id and set(by_sku) == {"EJ-1", "EJ-2", "EJ-3", "EJ-100", "EJ-101", "EJ-200"}
    assert by_sku["EJ-1"]["eligibility"] == "eligible" and by_sku["EJ-1"]["confidence"] in ("alta", "media")
    assert (by_sku["EJ-100"]["eligibility"], by_sku["EJ-100"]["confidence"]) == ("not_eligible", None)
    assert (by_sku["EJ-200"]["eligibility"], by_sku["EJ-200"]["confidence"]) == ("manual_review_only", "baja")
    assert all(set(v) == {"sku", "eligibility", "confidence"} for v in body["variants"])        # no ERP id, nothing else


def test_a_missing_token_is_refused(client):
    assert client.get("/forecasts/eligibility").status_code == 401
