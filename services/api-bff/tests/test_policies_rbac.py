"""T076 / T095: policy console routes - who may edit, revisions forwarded, sections independent, refusals are codes."""

from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient
from routes.api import get_inventory_client, get_procurement_client
from routes.policies import get_forecast_client
from tests_support import headers_for

BUYER = ["viewer", "buyer"]
APPROVER = ["viewer", "approver"]


def call(method, path, headers, proc=None, inv=None, fc=None, **kw):
    from main import app

    app.dependency_overrides[get_procurement_client] = lambda: proc or AsyncMock()
    app.dependency_overrides[get_inventory_client] = lambda: inv or AsyncMock()
    app.dependency_overrides[get_forecast_client] = lambda: fc or AsyncMock()
    try:
        return TestClient(app).request(method, path, headers=headers, **kw)
    finally:
        app.dependency_overrides.clear()


def refused(status, body):
    req = httpx.Request("PUT", "http://x")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(status, request=req, json=body))


def test_viewers_and_approvers_cannot_edit_policies_demand_rules_or_criticality(role_store):
    for roles in (["viewer"], APPROVER, ["viewer", "admin"]):
        h = headers_for("u", roles)
        for method, path, body in (("PUT", "/api/policies/global/*", {"min_units": 1}), ("POST", "/api/policies/global/*/preview", {"min_units": 1}), ("PUT", "/api/budget-caps", {}),
                                   ("PUT", "/api/stocking/1", {}), ("POST", "/api/policy-overrides", {}), ("PUT", "/api/products/5/criticality", {"critical": True}),
                                   ("POST", "/api/demand-rules/exclusions", {}), ("PUT", "/api/demand-rules/rules/min_zero_stock_days", {"value": 2}),
                                   ("PUT", "/api/parameters/lead_time", {"value": "9"}), ("POST", "/api/forecast/runs", {})):
            proc, inv, fc = AsyncMock(), AsyncMock(), AsyncMock()
            res = call(method, path, h, proc, inv, fc, json=body)
            assert res.status_code == 403 and res.json() == {"detail": "auth_forbidden_role"}, (roles, path)
            assert not (proc.forward.called or inv.forward.called or fc.forward.called)
    assert any(e["action"] == "access.refused" for e in role_store.audit_view())


def test_a_buyer_edit_forwards_the_user_and_the_revision_read(role_store):
    proc = AsyncMock()
    proc.forward.return_value = {"revision": 3}
    res = call("PUT", "/api/policies/segment/A", {**headers_for("buyer-1", BUYER), "If-Match": '"2"'}, proc, json={"service_level_pct": "97"})
    assert res.status_code == 200 and res.json() == {"revision": 3}
    args, kw = proc.forward.call_args
    assert args == ("PUT", "/policies/segment/A") and kw["json"] == {"service_level_pct": "97"} and kw["user_id"] == "buyer-1" and kw["if_match"] == '"2"'


def test_a_stale_revision_comes_back_as_412_with_the_current_one(role_store):
    proc = AsyncMock()
    proc.forward.side_effect = refused(412, {"detail": "revision_conflict", "current_version": 5})
    res = call("PUT", "/api/policies/global/*", {**headers_for("buyer-1", BUYER), "If-Match": '"2"'}, proc, json={"min_units": 1})
    assert res.status_code == 412 and res.json() == {"detail": "revision_conflict", "current_version": 5}


def test_only_an_approver_decides_overrides_and_a_buyer_can_request(role_store):
    proc = AsyncMock()
    proc.forward.return_value = {"status": "approved"}
    assert call("POST", "/api/policy-overrides/r1/approve", headers_for("b", BUYER), proc).status_code == 403
    assert call("POST", "/api/policy-overrides/r1/approve", headers_for("a", APPROVER), proc).status_code == 200
    assert call("POST", "/api/policy-overrides/r1/reject", headers_for("a", APPROVER), proc).status_code == 200
    proc.forward.return_value = {"id": "r1"}
    assert call("POST", "/api/policy-overrides", headers_for("b", BUYER), proc, json={"variant_id": 1}).status_code == 201


def test_the_console_composes_three_sections_and_one_failing_does_not_hide_the_others(role_store):
    proc, inv, fc = AsyncMock(), AsyncMock(), AsyncMock()
    proc.forward.return_value = {"policies": []}
    inv.forward.side_effect = httpx.ConnectError("down")
    fc.forward.return_value = {"parameters": []}
    body = call("GET", "/api/policy-console", headers_for("v", ["viewer"]), proc, inv, fc).json()
    assert body["purchasing"] == {"ok": True, "data": {"policies": []}} and body["forecast"]["ok"] is True
    assert body["demand"] == {"ok": False, "error": "downstream_unavailable"}


def test_a_criticality_change_is_forwarded_to_the_existing_inventory_endpoint(role_store):
    inv = AsyncMock()
    inv.forward.return_value = {"product_id": 5, "clinical_critical": True, "changed": True}
    res = call("PUT", "/api/products/5/criticality", headers_for("buyer-1", BUYER), inv=inv, json={"critical": True})
    assert res.status_code == 200 and inv.forward.call_args.args == ("PUT", "/products/5/criticality")
