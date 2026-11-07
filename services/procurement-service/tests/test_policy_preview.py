"""T074 + API: preview without saving, optimistic concurrency over HTTP, role checks."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from api import costs, policies
from conftest import add_supplier
from db.tables import audit_events, policy_sets
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from proposals.inputs import InputsProvider
from sqlalchemy import func, select
from test_inputs import ELIGIBLE, Src, cost, fc, stock, sv

D = Decimal
ROLES = {"buyer": {"viewer", "buyer"}, "approver": {"viewer", "approver"}, "buyer2": {"viewer", "buyer", "approver"}, "viewer": {"viewer"}}


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
        sa = add_supplier(c, 1, "A")
        cost(c, sa, 10, "1.00")
    app = create_service_app("procurement-service", validator=V())
    app.include_router(costs.build_router(app))
    app.include_router(policies.build_router(app))
    app.state.inputs_provider = InputsProvider(Src(stock(sv(1, 10, on_hand=0))), Src(fc(v1=ELIGIBLE)))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app)


def counts(engine):
    with engine.connect() as c:
        return c.execute(select(func.count()).select_from(policy_sets)).scalar(), c.execute(select(func.count()).select_from(audit_events)).scalar()


def test_preview_reports_affected_products_and_spend_change_and_saves_nothing(api, engine):
    before = counts(engine)
    r = api.post("/policies/global/*/preview", json={"service_level_pct": "99", "min_units": 40}, headers=h("buyer"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saved"] is False and body["affected_count"] == 1 and body["affected"][0]["variant_id"] == 1
    assert body["affected"][0]["qty_after"] > body["affected"][0]["qty_before"] and Decimal(body["spend_delta"]) > 0
    assert counts(engine) == before                                       # nothing saved, nothing audited


def test_preview_of_an_invalid_policy_is_refused_and_a_viewer_cannot_preview(api):
    assert api.post("/policies/global/*/preview", json={"min_units": 5, "max_units": 1}, headers=h("buyer")).json()["detail"] == "policy_out_of_range"
    assert api.post("/policies/global/*/preview", json={"min_units": 5}, headers=h("viewer")).status_code == 403


def test_save_requires_if_match_after_the_first_save_and_a_stale_one_is_a_412_with_the_current_revision(api):
    first = api.put("/policies/global/*", json={"service_level_pct": "95"}, headers=h("buyer"))
    assert first.status_code == 200 and first.json() == {"revision": 1}
    assert api.put("/policies/global/*", json={"service_level_pct": "96"}, headers=h("buyer")).status_code == 428
    assert api.put("/policies/global/*", json={"service_level_pct": "96"}, headers=h("buyer", **{"If-Match": '"1"'})).json() == {"revision": 2}
    stale = api.put("/policies/global/*", json={"service_level_pct": "97"}, headers=h("buyer", **{"If-Match": '"1"'}))
    assert stale.status_code == 412 and stale.json() == {"detail": "revision_conflict", "current_version": 2}
    got = api.get("/policies/global/*", headers=h("viewer")).json()
    assert got["revision"] == 2 and Decimal(got["current"]["service_level"]) == D("0.96") and [x["revision"] for x in got["history"]] == [1, 2]


def test_a_viewer_cannot_edit_and_out_of_range_values_are_422(api):
    assert api.put("/policies/global/*", json={"service_level_pct": "95"}, headers=h("viewer")).status_code == 403
    assert api.put("/policies/global/*", json={"service_level_pct": "20"}, headers=h("buyer")).json()["detail"] == "policy_out_of_range"
    assert api.put("/policies/segment/Q", json={"service_level_pct": "95"}, headers=h("buyer")).status_code == 422
    assert api.put("/budget-caps", json={"period": "week", "amount": "-5"}, headers=h("buyer")).status_code in (422,)


def test_budget_cap_and_listing(api):
    r = api.put("/budget-caps", json={"period": "week", "amount": "400"}, headers=h("buyer"))
    assert r.status_code == 200 and r.json()["weekly_budget"] == "400.00"
    api.put("/policies/segment/A", json={"service_level_pct": "97"}, headers=h("buyer"))
    lst = api.get("/policies", headers=h("viewer")).json()
    assert lst["weekly_budget"] == "400.00" and [(p["scope"], p["key"]) for p in lst["policies"]] == [("segment", "A")]


def test_stocking_and_override_endpoints_enforce_roles_and_separation(api):
    assert api.put("/stocking/1", json={"stocking_mode": "always_stocked", "min_floor_units": 0}, headers=h("buyer")).json()["detail"] == "stocking_floor_required"
    assert api.put("/stocking/1", json={"stocking_mode": "always_stocked", "min_floor_units": 1}, headers=h("buyer")).json() == {"revision": 1}
    assert api.put("/stocking/1", json={"stocking_mode": "standard", "min_floor_units": 0}, headers=h("buyer")).status_code == 428
    req = api.post("/policy-overrides", json={"variant_id": 1, "field": "safety_stock", "requested_value": 5, "reason": "proveedor poco fiable"}, headers=h("buyer"))
    assert req.status_code == 201 and req.json()["status"] == "pending"
    rid = req.json()["id"]
    assert api.post(f"/policy-overrides/{rid}/approve", headers=h("buyer")).status_code == 403                 # not an approver
    pending = api.get("/policy-overrides", headers=h("viewer")).json()
    assert [p["id"] for p in pending] == [rid]
    done = api.post(f"/policy-overrides/{rid}/approve", headers=h("buyer2"))
    assert done.status_code == 200 and done.json()["status"] == "approved"
    assert api.get("/policy-overrides", headers=h("viewer")).json() == []


def test_the_requester_cannot_approve_their_own_request(api):
    rid = api.post("/policy-overrides", json={"variant_id": 1, "field": "min", "requested_value": 3, "reason": "campaña de verano"}, headers=h("buyer2")).json()["id"]
    r = api.post(f"/policy-overrides/{rid}/approve", headers=h("buyer2"))
    assert r.status_code == 403 and r.json()["detail"] == "policy_override_self_approval"
    ok = api.post(f"/policy-overrides/{rid}/approve", headers=h("approver"))
    assert ok.status_code == 200 and ok.json()["status"] == "approved" and ok.json()["decided_by"] == "user-approver"
