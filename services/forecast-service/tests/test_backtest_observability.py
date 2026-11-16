"""T067 (forecast): a backtest job reports its outcome and duration in the log, and the log carries no secrets or personal data."""

import logging

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

        return Principal("buyer-secret-name", frozenset({"viewer", "buyer"}), None)


@pytest.fixture
def client(engine, make_export, tmp_path):
    export = make_export(seed=3)
    app = create_service_app("forecast-service", validator=_V())
    app.include_router(api.build_router(app))
    app.dependency_overrides[api.get_engine] = lambda: engine
    app.state.series_source = FakeSource(export)
    app.state.blob_writer = NullWriter(tmp_path)
    run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    return TestClient(app)


def test_a_finished_job_logs_outcome_and_duration_then_a_repeat_logs_reuse(client, caplog):
    with caplog.at_level(logging.INFO, logger="forecast.backtest"):
        client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H)
        client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H)
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("BACKTEST_JOB_DONE") and "duration_ms=" in m and "scope=catalogue" in m for m in messages)
    assert any(m.startswith("BACKTEST_JOB_REUSED") for m in messages)
    assert not any("buyer-secret-name" in m or "Bearer" in m for m in messages)


def test_a_failed_series_read_is_logged_without_the_error_text(client, caplog):
    class Broken:
        def fetch(self):
            raise RuntimeError("secret-token-123 at https://internal.example")

    client.app.state.series_source = Broken()
    with caplog.at_level(logging.INFO, logger="forecast.backtest"):
        r = client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H)
    assert r.status_code == 502
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("BACKTEST_JOB_FAILED") for m in messages)
    assert not any("secret-token-123" in m or "internal.example" in m for m in messages)
