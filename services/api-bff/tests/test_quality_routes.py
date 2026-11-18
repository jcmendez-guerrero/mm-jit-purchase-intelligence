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


URL = "/api/quality/products/EJ-9104/anomalies/2026-03-12"


def refusing_inventory():
    """Inventory-service refuses like the real one when it was not told the session has a fresh second factor."""
    inv = AsyncMock()
    req = httpx.Request("PUT", "http://x")

    async def forward(method, path, **kw):
        if method == "PUT" and (kw.get("extra_headers") or {}).get("X-Fresh-Second-Factor") != "true":
            raise httpx.HTTPStatusError("x", request=req, response=httpx.Response(403, request=req, json={"detail": "auth_mfa_stale"}))
        return OK

    inv.forward.side_effect = forward
    return inv


def test_the_gateway_only_reports_whether_the_session_has_a_fresh_second_factor(role_store):
    for age, expected in ((10, "true"), (301, "false")):
        inv = inventory()
        call("PUT", URL, headers_for("u", BUYER, mfa_age_seconds=age), inv, json={"decision": "excluded", "reason_code": "data_error"})
        assert len(puts(inv)) == 1 and puts(inv)[0].kwargs["extra_headers"] == {"X-Fresh-Second-Factor": expected}
        assert puts(inv)[0].kwargs["json"] == {"decision": "excluded", "reason_code": "data_error"}


def test_the_gateway_takes_no_domain_decision_and_never_reads_the_anomaly_state(role_store):
    for decision in ("excluded", "accepted"):
        inv = inventory(current=[{"day": "2026-03-12", "decision": "excluded"}])
        call("PUT", URL, headers_for("u", BUYER, mfa_age_seconds=5), inv, json={"decision": decision})
        assert [c.args[0] for c in inv.forward.call_args_list] == ["PUT"]


def test_a_refusal_from_inventory_for_a_stale_second_factor_keeps_its_code(role_store):
    for decision in ("excluded", "accepted"):
        r = call("PUT", URL, headers_for("u", BUYER, mfa_age_seconds=301), refusing_inventory(), json={"decision": decision, "reason_code": "data_error"})
        assert r.status_code == 403 and r.json() == {"detail": "auth_mfa_stale"}


def test_with_a_fresh_second_factor_buyers_and_admins_are_accepted(role_store):
    for roles in (BUYER, ADMIN):
        r = call("PUT", URL, headers_for("u", roles, mfa_age_seconds=10), refusing_inventory(), json={"decision": "excluded", "reason_code": "data_error"})
        assert r.status_code == 200


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
