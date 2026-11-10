"""T029 / T013 / T031 (feature 006): the overview takes a date range and the common filters, refuses malformed values before any service is called, and forwards the range
unchanged to every figure that depends on it. Nothing is guessed or coerced here: the range rules (span, order) belong to the domain service.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from routes.api import get_inventory_client, get_procurement_client
from routes.policies import get_forecast_client
from tests_support import headers_for


def call(query, roles=("buyer",)):
    from main import app

    inv, proc, fc = AsyncMock(), AsyncMock(), AsyncMock()
    inv.forward.return_value = {}
    proc.forward.return_value = []
    fc.forward.return_value = {"metrics": {}, "percent": {}}
    app.dependency_overrides[get_inventory_client] = lambda: inv
    app.dependency_overrides[get_procurement_client] = lambda: proc
    app.dependency_overrides[get_forecast_client] = lambda: fc
    try:
        return TestClient(app).get(f"/api/dashboard/overview{query}", headers=headers_for("u", list(roles))), inv, proc
    finally:
        app.dependency_overrides.clear()


def params_of(mock, path):
    return next(c for c in mock.forward.call_args_list if c.args[1] == path).kwargs["params"]


def test_the_range_reaches_the_trend_the_indicators_and_the_spend_unchanged(role_store):
    res, inv, proc = call("?date_from=2026-10-10&date_to=2026-10-19&supplier_id=sup-a")
    assert res.status_code == 200
    window = {"date_from": "2026-10-10", "date_to": "2026-10-19"}
    assert window.items() <= params_of(inv, "/dashboard/indicators").items()
    assert window.items() <= params_of(inv, "/dashboard/demand-trend").items()
    assert window.items() <= params_of(proc, "/summary/spend").items()


def test_only_one_end_given_the_other_follows_the_days_window(role_store):
    _res, inv, _proc = call("?date_to=2026-10-19&days=30")
    p = params_of(inv, "/dashboard/indicators")
    assert p["date_to"] == "2026-10-19" and p["date_from"] == "2026-09-20"
    _res, inv, _proc = call("?date_from=2026-10-10")
    assert params_of(inv, "/dashboard/indicators")["date_from"] == "2026-10-10"


def test_without_dates_the_days_window_still_applies(role_store):
    _res, inv, _proc = call("?days=30")
    p = params_of(inv, "/dashboard/indicators")
    assert p["date_from"] < p["date_to"] and params_of(inv, "/dashboard/demand-trend")["days"] == 30


@pytest.mark.parametrize("query", [
    "?date_from=2026-13-40", "?date_from=yesterday", "?date_to=2026-10-1", "?date_from=2026-10-10%27%3BDROP%20TABLE%20x", "?date_from=2026-10-10&date_to=",
    "?supplier_id=%27%20OR%201%3D1--", "?supplier_id=" + "a" * 37, "?category=Z", "?warehouse_id=-1", "?warehouse_id=abc", "?family=",
])
def test_malformed_values_are_refused_before_any_service_is_called(role_store, query):
    res, inv, proc = call(query)
    assert res.status_code == 422, query
    inv.forward.assert_not_called()
    proc.forward.assert_not_called()


def test_a_range_the_domain_refuses_degrades_only_its_own_cards(role_store):
    import httpx
    from main import app

    req = httpx.Request("GET", "http://inventory/x")
    inv = AsyncMock()
    inv.forward.side_effect = httpx.HTTPStatusError("x", request=req, response=httpx.Response(422, request=req))
    app.dependency_overrides[get_inventory_client] = lambda: inv
    app.dependency_overrides[get_procurement_client] = lambda: AsyncMock(forward=AsyncMock(return_value=[]))
    app.dependency_overrides[get_forecast_client] = lambda: AsyncMock(forward=AsyncMock(return_value={"metrics": {}, "percent": {}}))
    try:
        res = TestClient(app).get("/api/dashboard/overview?date_from=2026-10-10&date_to=2026-10-12", headers=headers_for("u", ["buyer"]))
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200 and res.json()["trend"] == {"ok": False, "error": "downstream_refused"}
