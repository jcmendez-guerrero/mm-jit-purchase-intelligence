"""T175 (FR-008): the buyer can see whether one product's forecast rests on imported estimates."""

import api
import pytest
from fastapi.testclient import TestClient
from mmi_common.service import create_service_app
from runs.runner import RunConfig, run_forecast
from test_seed_isolation import CLOCK, activate_valid, dense_csv, export_with_new_variant
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


def test_without_any_run_there_is_nothing_to_say(client):
    assert client.get("/forecasts/variant/9001", headers=H).status_code == 404


def test_a_seeded_variant_is_reported_as_resting_on_imported_estimates(client, engine, store, tmp_path):
    activate_valid(engine, store, dense_csv())
    run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    body = client.get("/forecasts/variant/9001", headers=H).json()
    assert body["variant_id"] == 9001 and body["eligible"] is True and body["seed_used"] is True and body["run_id"]


def test_a_variant_forecast_without_seeds_is_not_flagged(client, engine, tmp_path):
    run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    body = client.get("/forecasts/variant/9001", headers=H).json()
    assert body["seed_used"] is False and body["eligible"] is False


def test_an_unknown_variant_is_a_404_with_a_code(client, engine, tmp_path):
    run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    res = client.get("/forecasts/variant/424242", headers=H)
    assert res.status_code == 404 and res.json()["detail"] == "no_forecast_for_variant"
    assert client.get("/forecasts/variant/0", headers=H).status_code == 422
