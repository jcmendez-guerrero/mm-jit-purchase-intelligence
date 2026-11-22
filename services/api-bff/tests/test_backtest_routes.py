"""T056: BFF backtest routes - who may start one, forwarding, the running-job conflict and bad input."""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from routes.policies import get_forecast_client
from tests_support import headers_for

JOB = "11111111-1111-1111-1111-111111111111"


def call(method, path, headers, fc, **kw):
    from main import app

    app.dependency_overrides[get_forecast_client] = lambda: fc
    try:
        return TestClient(app).request(method, path, headers=headers, **kw)
    finally:
        app.dependency_overrides.clear()


def refusing(status, body):
    fc = AsyncMock()
    req = httpx.Request("POST", "http://x")
    fc.forward.side_effect = httpx.HTTPStatusError("x", request=req, response=httpx.Response(status, request=req, json=body))
    return fc


@pytest.mark.parametrize("roles", [["viewer", "buyer"], ["viewer", "admin"]])
def test_buyers_and_admins_start_a_backtest_and_the_body_is_forwarded(role_store, roles):
    fc = AsyncMock()
    fc.forward.return_value = {"job_id": JOB, "status": "completed"}
    r = call("POST", "/api/forecast/backtests", headers_for("u", roles), fc, json={"scope": "product", "sku": "EJ-1"})
    assert r.status_code == 200 and r.json()["job_id"] == JOB
    assert fc.forward.call_args.args[:2] == ("POST", "/forecasts/backtests") and fc.forward.call_args.kwargs["json"] == {"scope": "product", "sku": "EJ-1"}


@pytest.mark.parametrize("roles", [["viewer"], ["viewer", "approver"]])
def test_viewers_and_approvers_cannot_start_one(role_store, roles):
    fc = AsyncMock()
    assert call("POST", "/api/forecast/backtests", headers_for("u", roles), fc, json={"scope": "catalogue"}).status_code == 403
    fc.forward.assert_not_called()


def test_a_bad_scope_or_an_overlong_sku_is_refused_before_anything_downstream(role_store):
    fc = AsyncMock()
    h = headers_for("u", ["viewer", "buyer"])
    assert call("POST", "/api/forecast/backtests", h, fc, json={"scope": "everything"}).status_code == 422
    assert call("POST", "/api/forecast/backtests", h, fc, json={"scope": "product", "sku": "x" * 61}).status_code == 422
    fc.forward.assert_not_called()


def test_a_running_catalogue_backtest_keeps_its_code_and_names_the_job(role_store):
    r = call("POST", "/api/forecast/backtests", headers_for("u", ["viewer", "buyer"]), refusing(409, {"detail": "forecast_backtest_conflict", "running_job_id": JOB}), json={"scope": "catalogue"})
    assert r.status_code == 409 and r.json() == {"detail": "forecast_backtest_conflict", "running_job_id": JOB}


def test_a_running_job_id_that_is_not_a_uuid_is_never_echoed(role_store):
    r = call("POST", "/api/forecast/backtests", headers_for("u", ["viewer", "buyer"]), refusing(409, {"detail": "forecast_backtest_conflict", "running_job_id": "<script>"}), json={"scope": "catalogue"})
    assert r.status_code == 409 and r.json() == {"detail": "forecast_backtest_conflict"}


def test_a_failed_job_is_reported_as_unavailable_not_as_a_success(role_store):
    r = call("POST", "/api/forecast/backtests", headers_for("u", ["viewer", "buyer"]), refusing(502, {"detail": "quality_job_failed"}), json={"scope": "catalogue"})
    assert r.status_code >= 500 and r.status_code != 200


def test_any_signed_in_role_can_read_a_product_result_and_the_sku_is_encoded(role_store):
    fc = AsyncMock()
    fc.forward.return_value = {"sku": "a b", "beats_baseline": True}
    r = call("GET", "/api/forecast/products/a%20b/backtest", headers_for("u", ["viewer"]), fc)
    assert r.status_code == 200 and fc.forward.call_args.args[:2] == ("GET", "/forecasts/products/a%20b/backtest")
    assert call("GET", "/api/forecast/products/EJ-1/backtest", {}, AsyncMock()).status_code == 401
