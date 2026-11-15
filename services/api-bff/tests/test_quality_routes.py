"""T026: BFF quality routes - roles, the second factor for excluding or reversing an exclusion, and forwarding with a safe path."""

from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient
from routes.api import get_inventory_client
from tests_support import headers_for

BUYER = ["viewer", "buyer"]
ADMIN = ["viewer", "admin"]
OK = {"changed": True}


def call(method, path, headers, inv, **kw):
    from main import app

    app.dependency_overrides[get_inventory_client] = lambda: inv
    try:
        return TestClient(app).request(method, path, headers=headers, **kw)
    finally:
        app.dependency_overrides.clear()


def inventory(current=None):
    """Answers the anomaly list like inventory-service and accepts the decision."""
    inv = AsyncMock()

    async def forward(method, path, **kw):
        return {"anomalies": current or []} if method == "GET" and path.endswith("/anomalies") else OK

    inv.forward.side_effect = forward
    return inv


def puts(inv):
    return [c for c in inv.forward.call_args_list if c.args[0] == "PUT"]


def test_any_signed_in_role_can_read_and_the_sku_is_encoded(role_store):
    inv = inventory()
    r = call("GET", "/api/quality/products/EJ-9101?from=2026-01-01&to=2026-01-31", headers_for("u", ["viewer"]), inv)
    assert r.status_code == 200
    assert inv.forward.call_args.args[:2] == ("GET", "/quality/products/EJ-9101") and inv.forward.call_args.kwargs["params"] == {"from": "2026-01-01", "to": "2026-01-31"}
    call("GET", "/api/quality/products/a%20b", headers_for("u", ["viewer"]), inv)
    assert inv.forward.call_args.args[1] == "/quality/products/a%20b"


def test_unauthenticated_calls_are_refused(role_store):
    inv = inventory()
    assert call("GET", "/api/quality/products/EJ-9101", {}, inv).status_code == 401
    inv.forward.assert_not_called()


def test_viewers_and_approvers_cannot_decide_or_recompute(role_store):
    for roles in (["viewer"], ["viewer", "approver"]):
        inv = inventory()
        h = headers_for("u", roles)
        assert call("PUT", "/api/quality/products/EJ-9104/anomalies/2026-03-12", h, inv, json={"decision": "accepted"}).status_code == 403
        assert call("POST", "/api/quality/recompute", h, inv).status_code == 403
        inv.forward.assert_not_called()


def test_excluding_a_day_needs_a_fresh_second_factor_before_anything_downstream_runs(role_store):
    inv = inventory()
    r = call("PUT", "/api/quality/products/EJ-9104/anomalies/2026-03-12", headers_for("u", BUYER, mfa_age_seconds=301), inv, json={"decision": "excluded", "reason_code": "data_error"})
    assert r.status_code == 403 and r.json() == {"detail": "auth_mfa_stale"}
    inv.forward.assert_not_called()


def test_excluding_with_a_fresh_second_factor_is_forwarded_for_buyers_and_admins(role_store):
    for roles in (BUYER, ADMIN):
        inv = inventory()
        r = call("PUT", "/api/quality/products/EJ-9104/anomalies/2026-03-12", headers_for("u", roles, mfa_age_seconds=10), inv, json={"decision": "excluded", "reason_code": "data_error"})
        assert r.status_code == 200 and len(puts(inv)) == 1
        assert puts(inv)[0].kwargs["json"] == {"decision": "excluded", "reason_code": "data_error"}


def test_accepting_a_pending_day_needs_no_second_factor(role_store):
    inv = inventory(current=[{"day": "2026-03-12", "decision": "pending"}])
    r = call("PUT", "/api/quality/products/EJ-9104/anomalies/2026-03-12", headers_for("u", BUYER, mfa_age_seconds=9999), inv, json={"decision": "accepted"})
    assert r.status_code == 200 and len(puts(inv)) == 1


def test_reversing_an_exclusion_needs_a_fresh_second_factor(role_store):
    stale = inventory(current=[{"day": "2026-03-12", "decision": "excluded"}])
    r = call("PUT", "/api/quality/products/EJ-9104/anomalies/2026-03-12", headers_for("u", BUYER, mfa_age_seconds=301), stale, json={"decision": "accepted"})
    assert r.status_code == 403 and r.json() == {"detail": "auth_mfa_stale"} and puts(stale) == []
    fresh = inventory(current=[{"day": "2026-03-12", "decision": "excluded"}])
    assert call("PUT", "/api/quality/products/EJ-9104/anomalies/2026-03-12", headers_for("u", BUYER, mfa_age_seconds=5), fresh, json={"decision": "accepted"}).status_code == 200
    assert len(puts(fresh)) == 1


def test_a_bad_day_is_refused_before_the_downstream_call(role_store):
    inv = inventory()
    r = call("PUT", "/api/quality/products/EJ-9104/anomalies/not-a-date", headers_for("u", BUYER), inv, json={"decision": "accepted"})
    assert r.status_code == 422
    inv.forward.assert_not_called()


def test_recompute_is_forwarded_for_buyers_and_a_downstream_refusal_becomes_a_code(role_store):
    inv = inventory()
    assert call("POST", "/api/quality/recompute", headers_for("u", BUYER), inv).status_code == 200
    refusing = AsyncMock()
    req = httpx.Request("PUT", "http://x")
    refusing.forward.side_effect = httpx.HTTPStatusError("x", request=req, response=httpx.Response(404, request=req, json={"detail": "quality_product_not_found"}))
    r = call("GET", "/api/quality/products/NOPE", headers_for("u", ["viewer"]), refusing)
    assert r.status_code == 404 and "quality_product_not_found" in r.text
