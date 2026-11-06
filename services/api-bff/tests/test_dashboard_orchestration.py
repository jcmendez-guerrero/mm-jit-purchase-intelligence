"""T123: the BFF merges card-level results only and degrades per card when a service fails."""

from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient
from routes.api import get_inventory_client
from tests_support import headers_for


def call(path, headers, inv):
    from main import app

    app.dependency_overrides[get_inventory_client] = lambda: inv
    try:
        return TestClient(app).get(path, headers=headers)
    finally:
        app.dependency_overrides.clear()


def inventory(**cards):
    inv = AsyncMock()

    async def forward(method, path, **kw):
        out = cards.get(path)
        if isinstance(out, Exception):
            raise out
        return out if out is not None else {}

    inv.forward.side_effect = forward
    return inv


def test_all_cards_are_combined_and_filters_are_forwarded_unchanged(role_store):
    inv = inventory(**{"/dashboard/summary": {"inventory_value": "52.00"}, "/dashboard/demand-trend": {"series": []}, "/dashboard/abc-xyz": {"cells": []},
                       "/risk": [], "/dashboard/filters/options": {"warehouses": [], "categories": []}})
    res = call("/api/dashboard/overview?warehouse_id=2&category=A&days=30", headers_for("v", ["viewer"]), inv)
    body = res.json()
    assert res.status_code == 200 and set(body) == {"summary", "trend", "abc_xyz", "risks", "options"} and body["summary"] == {"ok": True, "data": {"inventory_value": "52.00"}}
    calls = {c.args[1]: c.kwargs for c in inv.forward.call_args_list}
    assert calls["/dashboard/summary"]["params"] == {"warehouse_id": 2, "category": "A"} and calls["/dashboard/demand-trend"]["params"] == {"warehouse_id": 2, "category": "A", "days": 30}
    assert calls["/risk"]["params"] == {"warehouse_id": 2} and calls["/dashboard/summary"]["user_id"] == "v"


def test_a_failing_card_degrades_alone(role_store):
    req = httpx.Request("GET", "http://inventory/x")
    inv = inventory(**{"/dashboard/summary": httpx.HTTPStatusError("x", request=req, response=httpx.Response(503, request=req)), "/dashboard/demand-trend": httpx.ConnectError("down"),
                       "/dashboard/abc-xyz": {"cells": [1]}, "/risk": [], "/dashboard/filters/options": {"warehouses": []}})
    body = call("/api/dashboard/overview", headers_for("v", ["viewer"]), inv).json()
    assert body["summary"] == {"ok": False, "error": "downstream_unavailable"} and body["trend"] == {"ok": False, "error": "downstream_unavailable"}
    assert body["abc_xyz"]["ok"] is True and body["options"]["ok"] is True


def test_filters_are_validated_and_authentication_is_required(role_store):
    inv = inventory()
    assert call("/api/dashboard/overview", {}, inv).status_code == 401
    assert call("/api/dashboard/overview?category=Z", headers_for("v", ["viewer"]), inv).status_code == 422
    assert call("/api/dashboard/overview?days=3", headers_for("v", ["viewer"]), inv).status_code == 422
    inv.forward.assert_not_called()
