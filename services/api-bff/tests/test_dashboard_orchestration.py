"""T123: the BFF merges card-level results only and degrades per card when a service fails."""

from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient
from routes.api import get_inventory_client, get_procurement_client
from routes.policies import get_forecast_client
from tests_support import headers_for


def call(path, headers, inv, proc=None, fc=None):
    from main import app

    app.dependency_overrides[get_inventory_client] = lambda: inv
    app.dependency_overrides[get_procurement_client] = lambda: proc or AsyncMock(forward=AsyncMock(return_value=[]))
    app.dependency_overrides[get_forecast_client] = lambda: fc or AsyncMock(forward=AsyncMock(return_value={"metrics": {}}))
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
    assert res.status_code == 200 and set(body) == {"summary", "trend", "abc_xyz", "risks", "options", "accuracy", "spend", "suppliers"} and body["summary"] == {"ok": True, "data": {"inventory_value": "52.00"}}
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


def test_spend_and_accuracy_come_from_their_own_services_and_fail_alone(role_store):
    inv = inventory(**{"/dashboard/summary": {"ok": 1}, "/dashboard/demand-trend": {}, "/dashboard/abc-xyz": {}, "/risk": [], "/dashboard/filters/options": {}})
    proc = AsyncMock()
    proc.forward.side_effect = lambda m, path, **kw: [{"id": "s1", "name": "Proveedor A", "terms": None}] if path == "/suppliers" else {"total": "95.00", "by_supplier": []}
    fc = AsyncMock()
    fc.forward.side_effect = httpx.ConnectError("down")
    body = call("/api/dashboard/overview?supplier_id=s1", headers_for("v", ["buyer"]), inv, proc, fc).json()      # spend is money: cost roles only
    assert body["spend"] == {"ok": True, "data": {"total": "95.00", "by_supplier": []}} and body["accuracy"] == {"ok": False, "error": "downstream_unavailable"}
    spend_call = next(c for c in proc.forward.call_args_list if c.args[1] == "/summary/spend")
    assert spend_call.kwargs["params"] == {"supplier_id": "s1"}
    assert body["suppliers"] == {"ok": True, "data": [{"id": "s1", "name": "Proveedor A"}]}


def test_the_product_family_is_forwarded_to_the_cards_and_validated():
    inv = AsyncMock()
    calls = {}

    async def fwd(method, path, **kw):
        calls[path] = kw
        return {}

    inv.forward.side_effect = fwd
    res = call("/api/dashboard/overview?family=Familia%20sint%C3%A9tica%20A&category=B", headers_for("v", ["viewer"]), inv)
    assert res.status_code == 200
    assert calls["/dashboard/summary"]["params"] == {"category": "B", "family": "Familia sintética A"}
    assert call("/api/dashboard/overview?family=" + "x" * 121, headers_for("v", ["viewer"]), inv).status_code == 422
    assert call("/api/dashboard/overview?family=", headers_for("v", ["viewer"]), inv).status_code == 422


def test_the_drilldown_forwards_the_figure_and_filters_for_the_signed_in_user_and_checks_the_shape():
    inv = AsyncMock()
    inv.forward.return_value = {"kind": "abc_xyz", "rows": [], "truncated": False, "total": 0}
    res = call("/api/dashboard/drilldown?kind=abc_xyz&abc=B&xyz=Y&warehouse_id=2&family=Fam", headers_for("v", ["viewer"]), inv)
    assert res.status_code == 200 and res.json()["kind"] == "abc_xyz"
    kw = inv.forward.call_args
    assert kw.args[:2] == ("GET", "/dashboard/drilldown") and kw.kwargs["params"] == {"kind": "abc_xyz", "abc": "B", "xyz": "Y", "warehouse_id": 2, "family": "Fam"}
    assert kw.kwargs["user_id"] == "v"
    inv.reset_mock()
    for bad in ("kind=drop_table", "kind=abc_xyz&abc=Q", "kind=trend_day&day=yesterday", "kind=coverage&category=Z", "kind=coverage&family="):
        assert call("/api/dashboard/drilldown?" + bad, headers_for("v", ["viewer"]), inv).status_code == 422, bad
    inv.forward.assert_not_called()
    assert call("/api/dashboard/drilldown?kind=coverage", {}, inv).status_code == 401


def test_the_forecast_basis_of_a_product_is_forwarded_as_the_signed_in_user():
    from routes.policies import get_forecast_client

    fc = AsyncMock()
    fc.forward.return_value = {"variant_id": 9001, "eligible": True, "seed_used": True, "horizons": [{"days": 14, "mean": 21.0, "upper": 27.5}], "upper_level": "0.95"}
    from main import app

    app.dependency_overrides[get_forecast_client] = lambda: fc
    try:
        client = TestClient(app)
        ok = client.get("/api/dashboard/variants/9001/forecast-basis", headers=headers_for("v", ["viewer"]))
        assert ok.status_code == 200 and ok.json()["seed_used"] is True and ok.json()["horizons"][0]["upper"] == 27.5          # the figures pass through unchanged
        assert fc.forward.call_args.args[:2] == ("GET", "/forecasts/variant/9001") and fc.forward.call_args.kwargs["user_id"] == "v"
        assert client.get("/api/dashboard/variants/0/forecast-basis", headers=headers_for("v", ["viewer"])).status_code == 422
        assert client.get("/api/dashboard/variants/9001/forecast-basis").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_the_supplier_filter_reaches_stock_figures_and_the_spend_card_and_a_bad_one_is_refused(role_store):
    inv = inventory(**{"/dashboard/summary": {"inventory_value": "42.00"}, "/dashboard/demand-trend": {"series": []}, "/dashboard/abc-xyz": {"cells": []},
                       "/risk": [], "/dashboard/filters/options": {"warehouses": [], "categories": []}, "/dashboard/drilldown": {"rows": [], "total": 0}})
    proc = AsyncMock(forward=AsyncMock(return_value=[]))
    res = call("/api/dashboard/overview?supplier_id=sup-a", headers_for("v", ["buyer"]), inv, proc)
    calls = {c.args[1]: c.kwargs for c in inv.forward.call_args_list}
    assert res.status_code == 200 and calls["/dashboard/summary"]["params"] == {"supplier_id": "sup-a"} and calls["/dashboard/demand-trend"]["params"] == {"supplier_id": "sup-a", "days": 60}
    assert any(c.kwargs.get("params") == {"supplier_id": "sup-a"} for c in proc.forward.call_args_list)
    assert call("/api/dashboard/overview?supplier_id=a%20b", headers_for("v", ["viewer"]), inventory()).status_code == 422
    drill = call("/api/dashboard/drilldown?kind=inventory_value&supplier_id=sup-a", headers_for("v", ["viewer"]), inv)
    assert drill.status_code == 200 and inv.forward.call_args.kwargs["params"] == {"kind": "inventory_value", "supplier_id": "sup-a"}
    assert call("/api/dashboard/drilldown?kind=inventory_value&supplier_id=a%20b", headers_for("v", ["viewer"]), inventory()).status_code == 422


def test_the_drilldown_page_is_forwarded_and_a_bad_page_is_refused(role_store):
    inv = inventory(**{"/dashboard/drilldown": {"rows": [], "total": 0}})
    res = call("/api/dashboard/drilldown?kind=inventory_value&limit=20&offset=40", headers_for("v", ["viewer"]), inv)
    assert res.status_code == 200 and inv.forward.call_args.kwargs["params"] == {"kind": "inventory_value", "limit": 20, "offset": 40}
    for bad in ("limit=0", "limit=500", "offset=-1"):
        assert call(f"/api/dashboard/drilldown?kind=inventory_value&{bad}", headers_for("v", ["viewer"]), inventory()).status_code == 422


def test_the_drilldown_sort_is_forwarded_and_a_bad_one_is_refused(role_store):
    inv = inventory(**{"/dashboard/drilldown": {"rows": [], "total": 0}})
    res = call("/api/dashboard/drilldown?kind=inventory_value&sort=sku&order=desc", headers_for("v", ["viewer"]), inv)
    assert res.status_code == 200 and inv.forward.call_args.kwargs["params"] == {"kind": "inventory_value", "sort": "sku", "order": "desc"}
    for bad in ("sort=variant_id", "order=sideways"):
        assert call(f"/api/dashboard/drilldown?kind=inventory_value&{bad}", headers_for("v", ["viewer"]), inventory()).status_code == 422


def test_the_spend_card_is_hidden_from_roles_without_cost_access_and_not_even_requested(role_store):
    inv = inventory(**{"/dashboard/summary": {}, "/dashboard/demand-trend": {"series": []}, "/dashboard/abc-xyz": {"cells": []}, "/risk": [], "/dashboard/filters/options": {}})
    proc = AsyncMock()
    proc.forward.side_effect = lambda m, path, **kw: [] if path == "/suppliers" else {"proposal_id": "p1", "total": "300.00"}
    viewer = call("/api/dashboard/overview", headers_for("v", ["viewer"]), inv, proc).json()
    assert viewer["spend"] == {"ok": False, "error": "hidden_by_role"}
    assert all(c.args[1] != "/summary/spend" for c in proc.forward.call_args_list)
    buyer = call("/api/dashboard/overview", headers_for("b", ["buyer"]), inv, proc).json()
    assert buyer["spend"] == {"ok": True, "data": {"proposal_id": "p1", "total": "300.00"}}
