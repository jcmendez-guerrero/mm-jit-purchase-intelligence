"""T051: backtest endpoints - roles, idempotency, one full-catalogue run at a time, no partial results after a failure, and the read endpoint."""

import api
import pytest
from db.tables import backtest_jobs, product_backtest
from fastapi.testclient import TestClient
from mmi_common.service import create_service_app
from runs.runner import run_forecast
from sqlalchemy import func, insert, select
from tests_helpers import FakeSource, NullWriter

H = {"Authorization": "Bearer x"}


class _V:
    def __init__(self, roles):
        self.roles = roles

    def validate(self, token, required_roles=()):
        from mmi_common.auth import Principal

        return Principal("svc", frozenset(self.roles), None)


def make_client(engine, export, tmp_path, roles=("viewer", "buyer")):
    app = create_service_app("forecast-service", validator=_V(roles))
    app.include_router(api.build_router(app))
    app.dependency_overrides[api.get_engine] = lambda: engine
    app.state.series_source = FakeSource(export)
    app.state.blob_writer = NullWriter(tmp_path)
    return TestClient(app)


@pytest.fixture
def client(engine, make_export, tmp_path):
    export = make_export(seed=3)
    run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    return make_client(engine, export, tmp_path)


def rows(engine):
    with engine.connect() as c:
        return c.execute(select(func.count()).select_from(product_backtest)).scalar()


def test_a_viewer_cannot_start_a_backtest(engine, make_export, tmp_path):
    export = make_export(seed=3)
    run_forecast(engine, FakeSource(export), NullWriter(tmp_path))
    viewer = make_client(engine, export, tmp_path, roles=("viewer",))
    assert viewer.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H).status_code == 403
    assert rows(engine) == 0


def test_a_catalogue_backtest_stores_one_result_per_assessable_product_and_reports_the_job(client, engine):
    r = client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H).json()
    assert r["status"] == "completed" and r["reused"] is False and r["products"] == 5 and r["job_id"]
    assert rows(engine) == 5


def test_identical_inputs_reuse_the_result_and_add_no_rows(client, engine):
    first = client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H).json()
    again = client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H).json()
    assert again["job_id"] == first["job_id"] and again["reused"] is True and rows(engine) == 5


def test_a_second_full_catalogue_request_while_one_runs_is_refused_naming_the_running_job(client, engine):
    with engine.begin() as c:
        c.execute(insert(backtest_jobs).values(id="11111111-1111-1111-1111-111111111111", scope="catalogue", status="running", requested_by="buyer-9",
                                               started_at=__import__("datetime").datetime(2026, 11, 15, tzinfo=__import__("datetime").UTC)))
    r = client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H)
    assert r.status_code == 409 and r.json()["detail"] == "forecast_backtest_conflict" and r.json()["running_job_id"] == "11111111-1111-1111-1111-111111111111"
    assert rows(engine) == 0


def test_a_product_backtest_is_allowed_while_a_catalogue_one_runs(client, engine):
    with engine.begin() as c:
        c.execute(insert(backtest_jobs).values(id="22222222-2222-2222-2222-222222222222", scope="catalogue", status="running", requested_by="buyer-9",
                                               started_at=__import__("datetime").datetime(2026, 11, 15, tzinfo=__import__("datetime").UTC)))
    r = client.post("/forecasts/backtests", json={"scope": "product", "sku": "EJ-1"}, headers=H)
    assert r.status_code == 200 and r.json()["products"] == 1


def test_a_failure_leaves_no_partial_results_and_frees_the_lock(engine, make_export, tmp_path):
    export = make_export(seed=3)
    run_forecast(engine, FakeSource(export), NullWriter(tmp_path))

    class Broken:
        def fetch(self):
            raise RuntimeError("inventory unreachable")

    bad = make_client(engine, export, tmp_path)
    bad.app.state.series_source = Broken()
    r = bad.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H)
    assert r.status_code == 502 and r.json()["detail"] == "quality_job_failed" and rows(engine) == 0
    with engine.connect() as c:
        assert c.execute(select(backtest_jobs.c.status)).scalars().all() == ["failed"]
    good = make_client(engine, export, tmp_path)
    assert good.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H).status_code == 200      # the failed job does not block a retry


def test_the_read_endpoint_returns_the_product_result_by_sku_with_versions(client, engine):
    client.post("/forecasts/backtests", json={"scope": "catalogue"}, headers=H)
    body = client.get("/forecasts/products/EJ-1/backtest", headers=H).json()
    assert body["sku"] == "EJ-1" and body["periods"] >= 0 and "variant_id" not in body and body["model_version"] and isinstance(body["beats_baseline"], bool)
    assert client.get("/forecasts/products/NOPE/backtest", headers=H).json()["detail"] == "quality_product_not_found"


def test_a_product_scope_needs_a_known_sku(client):
    assert client.post("/forecasts/backtests", json={"scope": "product"}, headers=H).status_code == 422
    assert client.post("/forecasts/backtests", json={"scope": "product", "sku": "NOPE"}, headers=H).json()["detail"] == "quality_product_not_found"
    assert client.post("/forecasts/backtests", json={"scope": "other"}, headers=H).status_code == 422
