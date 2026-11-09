"""T091 (FR-025, FR-003): capital tied up = stock at lot cost (inventory) + confirmed orders not yet received (procurement), composed here with Decimal.

Both parts are returned; the total is their exact sum; when a part is missing or the role has no cost access there is no value, never a total made of one part.
"""

from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient
from routes.api import get_inventory_client, get_procurement_client
from tests_support import headers_for

FRESH = {"source": "inventory_snapshot", "refreshed_at": "2026-11-09T08:00:00Z", "refreshed_at_original": None, "origin": "erp_sync", "state": "ok", "stale_after_hours": 48}


def stock_payload(value="100.00", state="ok"):
    return {"filters": {"date_from": "2026-09-11", "date_to": "2026-11-09"}, "indicators": [{"key": "stock_value", "value": value, "unit": "EUR", "state": state,
                                                                                            "basis": "dashboard.basis.lot_cost", "definition_key": "dashboard.def.stock_value", "freshness": FRESH}]}


def call(headers, inv_out, proc_out, query=""):
    from main import app

    inv, proc = AsyncMock(), AsyncMock()
    for svc, out in ((inv, inv_out), (proc, proc_out)):
        if isinstance(out, Exception):
            svc.forward.side_effect = out
        else:
            svc.forward.return_value = out
    app.dependency_overrides[get_inventory_client] = lambda: inv
    app.dependency_overrides[get_procurement_client] = lambda: proc
    try:
        return TestClient(app).get(f"/api/dashboard/capital{query}", headers=headers), inv, proc
    finally:
        app.dependency_overrides.clear()


def parts(body):
    return {p["key"]: p["value"] for p in body["parts"]}


def test_the_total_is_the_exact_sum_of_stock_at_cost_and_open_orders_and_both_parts_are_returned(role_store):
    res, _inv, _proc = call(headers_for("b", ["buyer"]), stock_payload("100.10"), {"open_orders": "29.95"})
    body = res.json()
    assert res.status_code == 200 and body["key"] == "capital_tied_up" and body["unit"] == "EUR" and body["state"] == "ok"
    assert body["value"] == "130.05" and parts(body) == {"stock_at_cost": "100.10", "open_orders": "29.95"} and body["freshness"]["source"] == "inventory_snapshot"
    assert body["definition_key"] == "dashboard.def.capital_tied_up"


def test_filters_reach_the_services_and_the_ones_open_orders_cannot_follow_are_named(role_store):
    res, inv, proc = call(headers_for("b", ["buyer"]), stock_payload(), {"open_orders": "0.00"}, "?supplier_id=sup-a&warehouse_id=2&category=A")
    assert inv.forward.call_args.kwargs["params"] == {"supplier_id": "sup-a", "warehouse_id": 2, "category": "A"}
    assert proc.forward.call_args.kwargs["params"] == {"supplier_id": "sup-a"}
    assert res.json()["filters_unsupported"] == ["warehouse", "category"]


def test_a_role_without_cost_access_gets_no_value_and_no_service_is_called(role_store):
    res, inv, proc = call(headers_for("v", ["viewer"]), stock_payload(), {"open_orders": "30.00"})
    body = res.json()
    assert body["state"] == "hidden_by_role" and body["value"] is None and "parts" not in body
    inv.forward.assert_not_called()
    proc.forward.assert_not_called()


def test_when_either_service_fails_the_state_is_error_with_no_value_and_no_partial_total(role_store):
    down = httpx.ConnectError("down")
    for inv_out, proc_out in ((stock_payload(), down), (down, {"open_orders": "30.00"})):
        body = call(headers_for("b", ["buyer"]), inv_out, proc_out)[0].json()
        assert body["state"] == "error" and body["value"] is None and "parts" not in body


def test_a_stock_part_that_is_not_a_number_or_open_orders_missing_is_an_error_not_a_sum(role_store):
    assert call(headers_for("b", ["buyer"]), stock_payload(None, "no_data"), {"open_orders": "30.00"})[0].json()["state"] == "error"
    assert call(headers_for("b", ["buyer"]), stock_payload(), {"total": "1.00"})[0].json()["state"] == "error"


def test_authentication_is_required_and_filters_are_validated(role_store):
    assert call({}, stock_payload(), {"open_orders": "1.00"})[0].status_code == 401
    assert call(headers_for("b", ["buyer"]), stock_payload(), {"open_orders": "1.00"}, "?category=Z")[0].status_code == 422
