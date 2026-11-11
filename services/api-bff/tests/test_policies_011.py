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


@pytest.mark.parametrize(("path", "body", "mock"), [("/api/parameters/lead_time", {"value": "9"}, "fc"), ("/api/demand-rules/rules/min_zero_stock_days", {"value": 3}, "inv")])
def test_forecast_parameters_and_censoring_rules_need_a_fresh_second_factor(role_store, path, body, mock):
    """T063 (owner decision): they change forecasts for every product, so they get the same check as budget caps."""
    target = fwd({"revision": 1})
    kw = {mock: target}
    stale = call("PUT", path, headers_for("buyer-1", BUYER, mfa_age_seconds=301), **kw, json=body)
    assert stale.status_code == 403 and stale.json() == {"detail": "auth_mfa_stale"}
    target.forward.assert_not_called()
    assert call("PUT", path, headers_for("buyer-1", BUYER, mfa_age_seconds=10), **kw, json=body).status_code == 200
    target.forward.assert_called_once()
    assert call("PUT", path, headers_for("v", ["viewer"], mfa_age_seconds=10), **kw, json=body).status_code == 403          # the role is checked first


def test_exclusions_keep_the_normal_session(role_store):
    inv = fwd({"id": 1})
    body = {"sku": None, "from_day": "2026-10-03", "to_day": "2026-10-03", "reason_code": "promotion"}
    assert call("POST", "/api/demand-rules/exclusions", headers_for("buyer-1", BUYER, mfa_age_seconds=3600), inv=inv, json=body).status_code == 201


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
    res = call("GET", "/api/policy-audit", headers_for("admin-1", ADMIN), proc, inv, fwd({"items": []}))
    assert res.status_code == 200
    actions = [i["action"] for i in res.json()["items"]]
    assert {"policy.saved", "demand_exclusion.added"} <= set(actions)
    refusals = [i for i in res.json()["items"] if i["outcome"] == "refused"]
    assert refusals and refusals[0]["actor"] == "viewer-1"
    ats = [i["at"] for i in res.json()["items"]]
    assert ats == sorted(ats, reverse=True)


def test_the_audit_view_filters_by_scope_outcome_and_dates_and_pages(role_store):
    """T070 (plan D9): scope, from, to, outcome, and 50 rows a page."""
    many = [{"at": f"2026-11-{d:02d}T10:00:00+00:00", "actor": "buyer-1", "action": "policy.saved", "outcome": "accepted"} for d in range(1, 29)]
    proc = fwd({"items": many + [{"at": "2026-11-09T09:00:00+00:00", "actor": "buyer-1", "action": "budget_cap.saved", "outcome": "accepted"}]})
    inv = fwd({"items": [{"at": "2026-11-09T11:00:00+00:00", "actor": "buyer-2", "action": "demand_exclusion.added", "outcome": "accepted"}]})
    fc = fwd({"items": [{"at": "2026-11-09T12:00:00+00:00", "actor": "buyer-3", "action": "parameter.saved", "outcome": "accepted"}]})
    call("PUT", "/api/policies/global/*", headers_for("viewer-1", ["viewer"]), AsyncMock(), json={"min_units": 1})                # one refusal recorded by the gateway
    get = lambda qs="": call("GET", f"/api/policy-audit{qs}", headers_for("admin-1", ADMIN), proc, inv, fc).json()          # noqa: E731

    everything = get()
    assert everything["total"] == 28 + 1 + 1 + 1 + 1 and len(everything["items"]) == 32 and everything["page"] == 1
    assert {i["action"] for i in get("?scope=budget")["items"]} == {"budget_cap.saved"}
    assert {i["action"] for i in get("?scope=demand")["items"]} == {"demand_exclusion.added"}
    assert {i["action"] for i in get("?scope=forecast")["items"]} == {"parameter.saved"}
    assert get("?scope=policy")["total"] == 28
    refused = get("?outcome=refused")
    assert refused["total"] == 1 and refused["items"][0]["actor"] == "viewer-1"
    day = get("?from=2026-11-09&to=2026-11-09")
    assert all(i["at"].startswith("2026-11-09") for i in day["items"]) and {"budget_cap.saved", "demand_exclusion.added", "parameter.saved", "policy.saved"} <= {i["action"] for i in day["items"]}
    assert call("GET", "/api/policy-audit?scope=nope", headers_for("admin-1", ADMIN), proc, inv, fc).status_code == 422
    assert call("GET", "/api/policy-audit?from=not-a-date", headers_for("admin-1", ADMIN), proc, inv, fc).status_code == 422


def test_the_audit_view_pages_fifty_rows_at_a_time(role_store):
    rows = [{"at": f"2026-10-{d:02d}T{h:02d}:00:00+00:00", "actor": "buyer-1", "action": "policy.saved", "outcome": "accepted"} for d in range(1, 29) for h in (8, 9, 10)]
    proc, empty = fwd({"items": rows}), fwd({"items": []})
    first = call("GET", "/api/policy-audit", headers_for("admin-1", ADMIN), proc, empty, empty).json()
    second = call("GET", "/api/policy-audit?page=2", headers_for("admin-1", ADMIN), proc, empty, empty).json()
    assert first["total"] == 84 and len(first["items"]) == 50 and len(second["items"]) == 34 and second["page"] == 2
    assert first["items"][0]["at"] > second["items"][0]["at"]                                              # newest first across pages


def test_the_audit_view_includes_forecast_parameter_changes_and_names_a_source_that_is_down(role_store):
    import httpx

    fc = fwd({"items": [{"at": "2026-11-09T12:00:00+00:00", "actor": "buyer-3", "action": "parameter.saved", "outcome": "accepted"}]})
    res = call("GET", "/api/policy-audit", headers_for("admin-1", ADMIN), fwd({"items": []}), fwd({"items": []}), fc)
    assert [i["action"] for i in res.json()["items"]] == ["parameter.saved"] and res.json()["unavailable"] == []
    down = AsyncMock()
    down.forward.side_effect = httpx.ConnectError("down")
    res2 = call("GET", "/api/policy-audit", headers_for("admin-1", ADMIN), fwd({"items": []}), fwd({"items": []}), down)
    assert res2.status_code == 200 and res2.json()["unavailable"] == ["forecast"]


def test_stocking_overrides_and_recommendation_are_addressed_by_sku_and_show_no_variant_id(role_store):
    """T054."""
    proc = fwd({"variant_id": 5, "sku": "SYN-0005", "stocking_mode": "standard", "min_floor_units": 0, "revision": 0})
    res = call("GET", "/api/stocking/SYN-0005", headers_for("v", ["viewer"]), proc)
    assert res.json() == {"sku": "SYN-0005", "stocking_mode": "standard", "min_floor_units": 0, "revision": 0}
    assert proc.forward.call_args.args[:2] == ("GET", "/stocking/SYN-0005")
    proc2 = fwd([{"id": "r1", "variant_id": 5, "sku": "SYN-0005", "field": "min", "status": "pending"}])
    assert call("GET", "/api/policy-overrides", headers_for("v", ["viewer"]), proc2).json() == [{"id": "r1", "sku": "SYN-0005", "field": "min", "status": "pending"}]
    proc3 = fwd({"variant_id": 5, "sku": "SYN-0005", "safety_stock": 4})
    assert call("GET", "/api/policy-overrides/recommendation/SYN-0005", headers_for("v", ["viewer"]), proc3).json() == {"sku": "SYN-0005", "safety_stock": 4}
    proc4 = fwd({"id": "r1", "variant_id": 5, "sku": "SYN-0005", "status": "approved"})
    for path in ("/api/policy-overrides/r1/approve", "/api/policy-overrides/r1/reject"):
        assert "variant_id" not in call("POST", path, headers_for("a", ["viewer", "approver"]), proc4).json()
    created = call("POST", "/api/policy-overrides", headers_for("b", BUYER), proc4, json={"sku": "SYN-0005", "field": "min", "requested_value": 3, "reason": "x"})
    assert created.status_code == 201 and "variant_id" not in created.json()


def test_the_category_history_has_a_sku_route(role_store):
    inv = fwd({"sku": "SYN-0005", "history": [{"reason_key": "first_classification"}]})
    res = call("GET", "/api/products/SYN-0005/segment-history", headers_for("v", ["viewer"]), inv=inv)
    assert res.status_code == 200 and res.json()["sku"] == "SYN-0005"
    assert inv.forward.call_args.args[:2] == ("GET", "/products/SYN-0005/segment-history")


def test_the_effective_policy_view_forwards_the_segments_of_the_product(role_store):
    proc = fwd({"sku": "SYN-0005", "rules": {}})
    inv = fwd({"segments": ["critical", "A"]})
    res = call("GET", "/api/products/SYN-0005/effective-policy", headers_for("v", ["viewer"]), proc, inv)
    assert res.status_code == 200
    assert proc.forward.call_args.kwargs["params"] == {"segments": "critical,A"}
