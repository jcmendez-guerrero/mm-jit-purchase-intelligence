"""T038: the BFF forecast explanation route - any signed-in role may read, the SKU is encoded, refusals become codes."""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from routes.policies import get_forecast_client
from tests_support import headers_for

BODY = {"run_id": "r1", "sku": "EJ-1", "eligibility": "eligible", "expected": "12.5000"}


def call(path, headers, fc):
    from main import app

    app.dependency_overrides[get_forecast_client] = lambda: fc
    try:
        return TestClient(app).get(path, headers=headers)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("roles", [["viewer"], ["viewer", "buyer"], ["viewer", "approver"], ["viewer", "admin"]])
def test_every_signed_in_role_can_read_it(role_store, roles):
    fc = AsyncMock()
    fc.forward.return_value = BODY
    r = call("/api/forecast/products/EJ-1/explanation", headers_for("u", roles), fc)
    assert r.status_code == 200 and r.json() == BODY
    assert fc.forward.call_args.args[:2] == ("GET", "/forecasts/products/EJ-1/explanation") and fc.forward.call_args.kwargs["params"] is None


def test_the_run_is_forwarded_and_the_sku_cannot_change_the_path(role_store):
    fc = AsyncMock()
    fc.forward.return_value = BODY
    call("/api/forecast/products/a%20b/explanation?run_id=abc", headers_for("u", ["viewer"]), fc)
    assert fc.forward.call_args.args[1] == "/forecasts/products/a%20b/explanation" and fc.forward.call_args.kwargs["params"] == {"run_id": "abc"}


def test_an_unauthenticated_call_is_refused_before_anything_downstream(role_store):
    fc = AsyncMock()
    assert call("/api/forecast/products/EJ-1/explanation", {}, fc).status_code == 401
    fc.forward.assert_not_called()


def test_an_overlong_run_id_is_refused(role_store):
    fc = AsyncMock()
    assert call(f"/api/forecast/products/EJ-1/explanation?run_id={'x' * 40}", headers_for("u", ["viewer"]), fc).status_code == 422
    fc.forward.assert_not_called()


def test_a_missing_explanation_becomes_its_code(role_store):
    fc = AsyncMock()
    req = httpx.Request("GET", "http://x")
    fc.forward.side_effect = httpx.HTTPStatusError("x", request=req, response=httpx.Response(404, request=req, json={"detail": "forecast_explanation_not_available"}))
    r = call("/api/forecast/products/EJ-1/explanation", headers_for("u", ["viewer"]), fc)
    assert r.status_code == 404 and "forecast_explanation_not_available" in r.text
