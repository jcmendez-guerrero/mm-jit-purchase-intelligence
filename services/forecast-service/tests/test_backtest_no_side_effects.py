"""T050: a backtest changes no stored forecast, explanation, run or other data (FR-017, SC-008)."""

import hashlib
import json

import api
import pytest
from db.tables import forecast_explanations, forecast_runs, forecast_values, metadata, product_backtest
from fastapi.testclient import TestClient
from mmi_common.service import create_service_app
from runs.runner import run_forecast
from sqlalchemy import select
from tests_helpers import FakeSource, NullWriter

H = {"Authorization": "Bearer x"}


class _V:
    def validate(self, token, required_roles=()):
        from mmi_common.auth import Principal

        return Principal("svc", frozenset({"viewer", "buyer"}), None)


def snapshot(engine, skip=("product_backtest", "backtest_jobs", "audit_events")):
    """A hash of every other table's content, so any write elsewhere shows."""
    out = {}
    with engine.connect() as c:
        for name, table in metadata.tables.items():
            if name in skip:
                continue
            rows = sorted(json.dumps([str(v) for v in r], sort_keys=True) for r in c.execute(select(table)).all())
            out[name] = hashlib.sha256("|".join(rows).encode()).hexdigest()
    return out


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


def test_a_catalogue_backtest_leaves_forecasts_explanations_and_runs_untouched(client, engine):
    before = snapshot(engine)
    r = client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H)
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert snapshot(engine) == before
    with engine.connect() as c:
        assert c.execute(select(product_backtest)).first() is not None
        assert c.execute(select(forecast_runs)).first() is not None and c.execute(select(forecast_values)).first() is not None
        assert c.execute(select(forecast_explanations)).first() is not None


def test_running_it_again_changes_nothing_else_either(client, engine):
    client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H)
    before = snapshot(engine)
    client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H)
    assert snapshot(engine) == before
