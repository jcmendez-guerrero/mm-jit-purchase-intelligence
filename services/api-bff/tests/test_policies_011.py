"""Feature 011 gateway rules (T021, T026, T027): fresh MFA on budget and global writes, revisions forwarded, no variant id in what the browser sees, audit view."""

from unittest.mock import AsyncMock

import pytest
from test_policies_rbac import call
from tests_support import headers_for

BUYER = ["viewer", "buyer"]
ADMIN = ["viewer", "buyer", "approver", "admin"]


def fwd(value):
    m = AsyncMock()
    m.forward.return_value = value
    return m


@pytest.mark.parametrize(("method", "path", "body"), [("PUT", "/api/policies/global/*", {"min_units": 1}), ("PUT", "/api/budget-caps", {"period": "week", "amount": "1"})])
def test_budget_and_global_writes_need_a_fresh_second_factor(role_store, method, path, body):
    proc = fwd({"revision": 1})
    res = call(method, path, headers_for("buyer-1", BUYER, mfa_age_seconds=301), proc, json=body)
    assert res.status_code == 403 and res.json() == {"detail": "auth_mfa_stale"}
    proc.forward.assert_not_called()
    assert any(e["action"] == "access.refused" and e["refusal_reason"] == "forbidden_mfa_stale" for e in role_store.audit_view())
    assert call(method, path, headers_for("buyer-1", BUYER, mfa_age_seconds=10), proc, json=body).status_code == 200
    proc.forward.assert_called_once()


@pytest.mark.parametrize("path", ["/api/policies/segment/A", "/api/policies/product/SYN-0001"])
def test_segment_and_product_writes_need_only_the_normal_session(role_store, path):
    proc = fwd({"revision": 1})
    assert call("PUT", path, headers_for("buyer-1", BUYER, mfa_age_seconds=3600), proc, json={"min_units": 1}).status_code == 200


def test_removing_an_override_is_a_buyer_action_with_the_revision_and_global_needs_a_fresh_factor(role_store):
    proc = fwd({"revision": 2})
    assert call("DELETE", "/api/policies/product/SYN-0001", {**headers_for("v", ["viewer"]), "If-Match": '"1"'}, proc).status_code == 403
    proc.forward.assert_not_called()
    ok = call("DELETE", "/api/policies/product/SYN-0001", {**headers_for("buyer-1", BUYER, mfa_age_seconds=3600), "If-Match": '"1"'}, proc)
    assert ok.status_code == 200 and proc.forward.call_args.kwargs["if_match"] == '"1"' and proc.forward.call_args.args[:2] == ("DELETE", "/policies/product/SYN-0001")
    stale = call("DELETE", "/api/policies/global/*", {**headers_for("buyer-1", BUYER, mfa_age_seconds=301), "If-Match": '"1"'}, fwd({}))
    assert stale.status_code == 403 and stale.json() == {"detail": "auth_mfa_stale"}


def test_a_budget_save_forwards_the_revision_read(role_store):
    proc = fwd({"revision": 2})
    res = call("PUT", "/api/budget-caps", {**headers_for("buyer-1", BUYER), "If-Match": '"1"'}, proc, json={"period": "week", "amount": "9"})
    assert res.status_code == 200 and proc.forward.call_args.kwargs["if_match"] == '"1"'


def test_the_preview_and_the_console_never_show_a_variant_id(role_store):
    proc = fwd({"affected": [{"variant_id": 5, "sku": "SYN-0005", "qty_before": 1, "qty_after": 2}], "saved": False})
    res = call("POST", "/api/policies/global/*/preview", headers_for("buyer-1", BUYER), proc, json={"min_units": 1})
    assert res.json()["affected"] == [{"sku": "SYN-0005", "qty_before": 1, "qty_after": 2}]
    proc2 = fwd({"policies": [{"scope": "product", "key": "SYN-0005", "variant_id": 5, "revision": 1}], "orphaned": []})
    res2 = call("GET", "/api/policy-console", headers_for("v", ["viewer"]), proc2, inv=fwd({"exclusions": [], "rules": []}), fc=fwd({"parameters": []}))
    assert res2.json()["purchasing"]["data"]["policies"] == [{"scope": "product", "key": "SYN-0005", "revision": 1}]


def test_the_audit_view_is_admin_only(role_store):
    for roles in (["viewer"], BUYER, ["viewer", "approver"]):
        res = call("GET", "/api/policy-audit", headers_for("u", roles), fwd({"items": []}), fwd({"items": []}))
        assert res.status_code == 403


def test_the_audit_view_merges_services_and_refusals_newest_first(role_store):
    proc = fwd({"items": [{"at": "2026-11-09T10:00:00+00:00", "actor": "buyer-1", "action": "policy.saved", "outcome": "accepted"}]})
    inv = fwd({"items": [{"at": "2026-11-09T11:00:00+00:00", "actor": "buyer-2", "action": "demand_exclusion.added", "outcome": "accepted"}]})
    call("PUT", "/api/policies/global/*", headers_for("viewer-1", ["viewer"]), AsyncMock(), json={"min_units": 1})        # a refused edit: recorded by the gateway
    res = call("GET", "/api/policy-audit", headers_for("admin-1", ADMIN), proc, inv)
    assert res.status_code == 200
    actions = [i["action"] for i in res.json()["items"]]
    assert {"policy.saved", "demand_exclusion.added"} <= set(actions)
    refusals = [i for i in res.json()["items"] if i["outcome"] == "refused"]
    assert refusals and refusals[0]["actor"] == "viewer-1"
    ats = [i["at"] for i in res.json()["items"]]
    assert ats == sorted(ats, reverse=True)


def test_the_effective_policy_view_forwards_the_segments_of_the_product(role_store):
    proc = fwd({"sku": "SYN-0005", "rules": {}})
    inv = fwd({"segments": ["critical", "A"]})
    res = call("GET", "/api/products/SYN-0005/effective-policy", headers_for("v", ["viewer"]), proc, inv)
    assert res.status_code == 200
    assert proc.forward.call_args.kwargs["params"] == {"segments": "critical,A"}
