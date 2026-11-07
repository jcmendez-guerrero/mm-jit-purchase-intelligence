"""T175 (FR-008): the buyer can see whether one product's forecast rests on imported estimates."""

from datetime import timedelta

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


def test_an_eligible_variant_returns_its_mean_and_upper_bound_per_horizon(client, engine, store, tmp_path):
    activate_valid(engine, store, dense_csv())
    run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    body = client.get("/forecasts/variant/9001", headers=H).json()
    hs = body["horizons"]
    assert [h["days"] for h in hs] == sorted(h["days"] for h in hs) and len(hs) >= 3
    assert all(h["mean"] is not None and h["upper"] is not None and h["upper"] >= h["mean"] for h in hs)
    assert body["upper_level"] == "0.95"


def test_a_conservative_min_max_variant_has_no_horizon_figures(client, engine, tmp_path):
    run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    body = client.get("/forecasts/variant/9001", headers=H).json()
    assert body["eligible"] is False and body["horizons"] == []                        # no mean to show; the page says it uses min/max


def test_the_latest_forecast_names_the_run_and_the_dataset_behind_it(client, engine, store, tmp_path):
    run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    plain = client.get("/forecasts/latest", headers=H).json()
    assert plain["run_id"] and plain["dataset_version_id"] is None                       # no active dataset: nothing is invented
    did = activate_valid(engine, store, dense_csv())
    run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=lambda: CLOCK() + timedelta(hours=1))      # a later run is the latest
    seeded_run = client.get("/forecasts/latest", headers=H).json()
    assert seeded_run["dataset_version_id"] == did and seeded_run["run_id"] != plain["run_id"]


def test_the_completion_event_carries_the_dataset_version(engine, store, tmp_path):
    import json

    from db.tables import outbox
    from sqlalchemy import select

    did = activate_valid(engine, store, dense_csv())
    run_forecast(engine, FakeSource(export_with_new_variant()), NullWriter(tmp_path), RunConfig(), clock=CLOCK)
    with engine.connect() as c:
        rows = c.execute(select(outbox)).all()
    docs = [json.loads(p.read_text()) for p in (tmp_path / "events" / "forecast").glob("*.json")]
    assert docs and all(d["dataset_version_id"] == did for d in docs) and rows
