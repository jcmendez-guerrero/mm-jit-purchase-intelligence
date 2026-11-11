"""Feature 011 over HTTP (T019, T021 service side, T023, T013, T016): budget revisions, SKU keys, effective-policy view and the audit read."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from api import costs, policies
from db.tables import product_refs
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from sqlalchemy import insert

ROLES = {"buyer": {"viewer", "buyer"}, "viewer": {"viewer"}, "admin": {"viewer", "buyer", "approver", "admin"}}


class V:
    def validate(self, token, required_roles=()):
        roles = ROLES.get(token)
        if roles is None or not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(f"user-{token}", frozenset(roles), datetime.now(UTC) - timedelta(minutes=1))


def h(role, **extra):
    return {"Authorization": f"Bearer {role}", **extra}


@pytest.fixture
def api(engine):
    with engine.begin() as c:
        c.execute(insert(product_refs).values(variant_id=5, product_id=5, sku="SYN-0005", name="Producto sintético"))
    app = create_service_app("procurement-service", validator=V())
    app.include_router(costs.build_router(app))
    app.include_router(policies.build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app)


CAP = {"period": "week", "scope": "global", "amount": "500.00"}


def test_a_category_cap_is_422_budget_scope_unsupported_and_nothing_is_stored(api):
    r = api.put("/budget-caps", json={"period": "week", "scope": "category", "scope_key": "antiparasitarios", "amount": "100"}, headers=h("buyer"))
    assert r.status_code == 422 and r.json()["detail"] == "budget_scope_unsupported"
    assert api.get("/policies", headers=h("viewer")).json()["weekly_budget_revision"] == 0
    assert api.put("/budget-caps", json={"period": "week", "scope": "supplier", "scope_key": "sup-1", "amount": "100"}, headers=h("buyer")).status_code == 200


def test_the_first_budget_cap_needs_no_revision_and_returns_one(api):
    assert api.get("/policies", headers=h("viewer")).json()["weekly_budget_revision"] == 0
    r = api.put("/budget-caps", json=CAP, headers=h("buyer"))
    assert r.status_code == 200 and r.json()["revision"] == 1
    assert api.get("/policies", headers=h("viewer")).json()["weekly_budget_revision"] == 1


def test_a_later_budget_cap_save_without_a_revision_is_428(api):
    api.put("/budget-caps", json=CAP, headers=h("buyer"))
    assert api.put("/budget-caps", json=CAP, headers=h("buyer")).status_code == 428


def test_a_stale_budget_cap_save_is_412_with_the_current_revision(api):
    api.put("/budget-caps", json=CAP, headers=h("buyer"))
    api.put("/budget-caps", json={**CAP, "amount": "600"}, headers=h("buyer", **{"If-Match": '"1"'}))
    r = api.put("/budget-caps", json={**CAP, "amount": "700"}, headers=h("buyer", **{"If-Match": '"1"'}))
    assert r.status_code == 412 and r.json() == {"detail": "revision_conflict", "current_version": 2}


def test_a_product_policy_is_addressed_by_sku(api):
    r = api.put("/policies/product/SYN-0005", json={"min_units": 3}, headers=h("buyer"))
    assert r.status_code == 200 and r.json() == {"revision": 1}
    got = api.get("/policies/product/syn-0005", headers=h("viewer")).json()
    assert got["revision"] == 1 and got["current"]["min_units"] == "3"
    listed = api.get("/policies", headers=h("viewer")).json()["policies"]
    assert [p["key"] for p in listed if p["scope"] == "product"] == ["SYN-0005"]


@pytest.mark.parametrize("sku", ["NOPE", "5"])
def test_an_unknown_sku_or_a_raw_variant_id_is_refused(api, sku):
    r = api.put(f"/policies/product/{sku}", json={"min_units": 3}, headers=h("buyer"))
    assert r.status_code == 422 and r.json()["detail"] == "sku_unknown"


def test_a_save_dated_before_a_scheduled_revision_is_422_policy_overlap(api):
    future = (datetime.now(UTC).date() + timedelta(days=10)).isoformat()
    assert api.put("/policies/global/*", json={"min_units": 1, "valid_from": future}, headers=h("buyer")).status_code == 200
    r = api.put("/policies/global/*", json={"min_units": 2}, headers=h("buyer", **{"If-Match": '"1"'}))
    assert r.status_code == 422 and r.json()["detail"] == "policy_overlap"


def test_the_effective_view_shows_sources_and_defaults(api):
    api.put("/policies/global/*", json={"service_level_pct": "90"}, headers=h("buyer"))
    api.put("/policies/product/SYN-0005", json={"min_units": 3}, headers=h("buyer"))
    body = api.get("/products/SYN-0005/effective-policy", headers=h("viewer")).json()
    assert body["rules"]["service_level"]["source"] == "global"
    assert body["rules"]["min_units"]["source"] == "product" and body["rules"]["min_units"]["value"] == "3"
    assert body["rules"]["max_units"]["source"] == "default"


def test_the_audit_read_is_admin_only_and_lists_changes(api):
    api.put("/policies/global/*", json={"min_units": 1}, headers=h("buyer"))
    api.put("/budget-caps", json=CAP, headers=h("buyer"))
    assert api.get("/policy-audit", headers=h("buyer")).status_code == 403
    items = api.get("/policy-audit", headers=h("admin")).json()["items"]
    assert {i["action"] for i in items} >= {"policy.saved", "budget_cap.saved"}
    assert all(i["actor"] and i["at"] for i in items) and all(i["outcome"] == "accepted" for i in items)


def test_audit_events_carry_the_previous_value_and_the_revision(api):
    """T056: who changed what from which value to which."""
    api.put("/policies/global/*", json={"min_units": 1}, headers=h("buyer"))
    api.put("/policies/global/*", json={"min_units": 4}, headers={**h("buyer"), "If-Match": '"1"'})
    api.delete("/policies/global/*", headers={**h("buyer"), "If-Match": '"2"'})
    api.put("/budget-caps", json=CAP, headers=h("buyer"))
    api.put("/budget-caps", json={**CAP, "amount": "700"}, headers={**h("buyer"), "If-Match": '"1"'})
    items = {(i["action"], (i["after"] or {}).get("revision")): i for i in api.get("/policy-audit", headers=h("admin")).json()["items"]}
    first, second, cleared = items[("policy.saved", 1)], items[("policy.saved", 2)], items[("policy.cleared", 3)]
    assert first["before"] is None
    assert second["before"]["min_units"] == "1" and second["before"]["revision"] == 1 and second["after"]["min_units"] == "4"
    assert cleared["before"]["min_units"] == "4" and cleared["before"]["revision"] == 2
    cap = items[("budget_cap.saved", 2)]
    assert Decimal(cap["before"]["amount"]) == Decimal("500") and cap["before"]["revision"] == 1 and cap["after"]["amount"] == "700"


def test_the_audit_view_shows_skus_and_never_an_erp_id_or_typed_text(api):
    """T067 (FR-018, FR-013): product policies, stocking and override requests are audited by variant id inside; the view shows the SKU and no typed reason."""
    api.put("/policies/product/SYN-0005", json={"min_units": 3}, headers=h("buyer"))
    api.put("/stocking/SYN-0005", json={"stocking_mode": "always_stocked", "min_floor_units": 2}, headers=h("buyer"))
    rid = api.post("/policy-overrides", json={"sku": "SYN-0005", "field": "min", "requested_value": 9, "reason": "proveedor poco fiable este mes"}, headers=h("buyer")).json()["id"]
    assert api.post(f"/policy-overrides/{rid}/approve", headers=h("admin")).status_code == 200
    items = api.get("/policy-audit", headers=h("admin")).json()["items"]
    text = str(items)
    assert "variant_id" not in text and "proveedor poco fiable" not in text                             # no ERP id, no typed reason
    by_action = {i["action"]: i for i in items}
    assert by_action["policy.saved"]["after"]["key"] == "SYN-0005" and by_action["policy.saved"]["after"]["scope"] == "product"
    assert by_action["stocking.saved"]["entity_id"] == "SYN-0005" and by_action["stocking.saved"]["after"] == {"mode": "always_stocked", "floor": 2, "revision": 1}
    assert by_action["policy_override.requested"]["entity_id"] == "SYN-0005" and by_action["policy_override.requested"]["after"]["requested"] == 9
    assert by_action["policy_override.approved"]["entity_id"] == "SYN-0005"
    assert all(i["entity_id"] != "5" for i in items)


def test_the_preview_rows_carry_the_sku(api):
    from proposals.inputs import InputsProvider
    from test_inputs import ELIGIBLE, Src, fc, stock, sv
    api.app.state.inputs_provider = InputsProvider(Src(stock(sv(5, 10, on_hand=0))), Src(fc(v5=ELIGIBLE)))
    r = api.post("/policies/global/*/preview", json={"min_units": 40}, headers=h("buyer"))
    assert r.status_code == 200, r.text
    assert all(row["sku"] == "SYN-0005" for row in r.json()["affected"])
    assert r.json()["forecast_run_id"] == "run-1"                                                    # T071: the preview says which forecast run it was computed with


def test_the_audit_filters_run_before_the_row_limit(api):
    """T073: an old budget change is found by its filter even when newer policy changes fill the limit."""
    api.put("/budget-caps", json=CAP, headers=h("buyer"))
    for n in (1, 2, 3):
        api.put("/policies/global/*", json={"min_units": n}, headers=h("buyer") if n == 1 else {**h("buyer"), "If-Match": f'"{n - 1}"'})
    newest = api.get("/policy-audit?limit=1", headers=h("admin")).json()["items"]
    assert [i["action"] for i in newest] == ["policy.saved"]
    assert [i["action"] for i in api.get("/policy-audit?limit=1&prefix=budget_cap.", headers=h("admin")).json()["items"]] == ["budget_cap.saved"]
    assert api.get("/policy-audit?outcome=refused", headers=h("admin")).json()["items"] == []
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert api.get("/policy-audit", params={"since": tomorrow}, headers=h("admin")).json()["items"] == []
    assert api.get("/policy-audit", params={"until": tomorrow}, headers=h("admin")).json()["items"] != []
