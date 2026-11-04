"""T105: proposal, order and cost-write endpoints."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from api import costs, proposals
from builders import flat_forecast, inputs, offer, terms, variant
from conftest import add_supplier
from costs.rules import CostRules
from costs.store import NewCost, add_version
from db.tables import erp_supplier_links
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from sqlalchemy import insert

D = Decimal
ROLES = {"buyer": {"viewer", "buyer"}, "buyer2": {"viewer", "buyer"}, "approver": {"viewer", "approver"}, "buyerapprover": {"viewer", "buyer", "approver"},
         "viewer": {"viewer"}, "writer": {"cost-writer"}, "stale": {"viewer", "approver"}}


class Validator:
    def validate(self, token, required_roles=()):
        roles = ROLES.get(token)
        if roles is None or not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        auth_time = datetime.now(UTC) - timedelta(minutes=30 if token == "stale" else 1)  # noqa: S105 - test token name
        return Principal(f"user-{token}", frozenset(roles), auth_time)


class Provider:
    def __init__(self, supplier):
        self.supplier = supplier

    def build(self, today):
        return inputs([variant(1, [offer(self.supplier, "1.00", pack=6)], flat_forecast(1.0))], [terms(self.supplier)], budget="1000")


class Users:
    def active_approvers(self):
        return {"user-approver", "user-buyerapprover"}


class Blob:
    def __init__(self, tmp):
        self.tmp = tmp

    def put(self, name, data):
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()


def h(role, **extra):
    return {"Authorization": f"Bearer {role}", **extra}


@pytest.fixture
def api(engine, tmp_path):
    with engine.begin() as c:
        sid = add_supplier(c, 1, "Proveedor Sintetico")
        add_version(c, NewCost(product_id=10, supplier_id=sid, cost_with_recargo=D("1.00"), source="siweb_product_supplier", actor="siweb-import", pack_size=6), CostRules())
        c.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=sid, has_cost=True, last_seen_at=datetime.now(UTC)))
    app = create_service_app("procurement-service", validator=Validator())
    app.include_router(costs.build_router(app))
    app.include_router(proposals.build_router(app))
    app.state.inputs_provider, app.state.user_directory, app.state.blob_writer = Provider(sid), Users(), Blob(tmp_path)
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app), sid


def generate(client):
    r = client.post("/proposals", headers=h("buyer"))
    assert r.status_code == 202
    return r.json()["id"]


def test_roles_are_enforced_on_every_proposal_endpoint(api):
    c, _sid = api
    pid = generate(c)
    assert c.post("/proposals", headers=h("viewer")).status_code == 403
    assert c.get("/proposals").status_code == 401
    assert c.post(f"/proposals/{pid}/submit", headers=h("viewer")).status_code == 403
    assert c.post(f"/proposals/{pid}/approve", headers=h("buyer")).status_code == 403
    assert c.get(f"/proposals/{pid}/export?format=csv", headers=h("viewer")).status_code == 403


def test_unconfigured_dependencies_fail_closed(engine):
    app = create_service_app("procurement-service", validator=Validator())
    app.include_router(proposals.build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    assert TestClient(app).post("/proposals", headers=h("buyer")).status_code == 503


def test_generate_read_edit_with_if_match_and_explanations(api):
    c, sid = api
    pid = generate(c)
    p = c.get(f"/proposals/{pid}", headers=h("viewer")).json()
    line = p["lines"][0]
    assert p["status"] == "draft" and p["version"] == 1 and line["explanation"]["supplier"]["chosen"] == sid and p["supplier_groups"][0]["supplier_id"] == sid
    assert [x["id"] for x in c.get("/proposals", headers=h("viewer")).json()] == [pid]
    ok = c.patch(f"/proposals/{pid}/lines/{line['id']}", json={"qty": line["qty"] + 6}, headers=h("buyer2", **{"If-Match": "1"}))
    assert ok.status_code == 200 and ok.json()["version"] == 2 and ok.json()["last_edited_by"] == "user-buyer2"
    assert c.patch(f"/proposals/{pid}/lines/{line['id']}", json={"qty": 12}, headers=h("buyer", **{"If-Match": "1"})).status_code == 409        # stale version
    assert c.patch(f"/proposals/{pid}/lines/{line['id']}", json={"qty": 7}, headers=h("buyer", **{"If-Match": "2"})).status_code == 422          # not a pack multiple
    assert c.patch(f"/proposals/{pid}/lines/nope", json={"qty": 6}, headers=h("buyer")).status_code == 404
    assert c.patch(f"/proposals/{pid}/lines/{line['id']}", json={"qty": 6}, headers=h("buyer", **{"If-Match": "x"})).status_code == 400


def test_full_flow_submit_approve_export_confirm(api):
    c, sid = api
    pid = generate(c)
    assert c.post(f"/proposals/{pid}/approve", headers=h("approver")).status_code == 409                                                       # not submitted
    assert c.post(f"/proposals/{pid}/submit", headers=h("buyer")).status_code == 200
    assert c.post(f"/proposals/{pid}/approve", headers=h("stale")).status_code == 403                                                          # stale second factor
    assert c.post(f"/proposals/{pid}/approve", headers=h("approver")).json() == {"status": "approved"}
    p = c.get(f"/proposals/{pid}", headers=h("viewer")).json()
    assert p["approval"]["valid"] and p["status"] == "approved"
    csv = c.get(f"/proposals/{pid}/export?format=csv", headers=h("buyer"))
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv") and b"Proveedor;" in csv.content
    assert c.get(f"/proposals/{pid}/export?format=xlsx", headers=h("buyer")).status_code == 200
    assert c.get(f"/proposals/{pid}/export?format=pdf", headers=h("buyer")).status_code == 422
    line = p["lines"][0]
    done = c.post(f"/proposals/{pid}/orders/{sid}/confirm", json={"lines": [{"variant_id": 1, "qty": line["qty"], "cost_with_recargo": "1.20"}]}, headers=h("buyer"))
    assert done.status_code == 201 and done.json()["cost_writes"][0]["status"] == "pending_review"
    assert c.post(f"/proposals/{pid}/orders/{sid}/confirm", json={"lines": [{"variant_id": 1, "qty": 1, "cost_with_recargo": "1"}]}, headers=h("buyer")).status_code == 409


def test_the_creator_with_both_roles_still_cannot_approve_their_own_proposal(api):
    c, _sid = api
    r = c.post("/proposals", headers=h("buyerapprover"))
    pid = r.json()["id"]
    assert c.post(f"/proposals/{pid}/submit", headers=h("buyerapprover")).status_code == 200
    denied = c.post(f"/proposals/{pid}/approve", headers=h("buyerapprover"))
    assert denied.status_code == 403 and denied.json()["detail"] == "separation_of_duties"


def test_cost_write_review_release_and_internal_view_for_the_writer(api):
    c, sid = api
    pid = generate(c)
    c.post(f"/proposals/{pid}/submit", headers=h("buyer"))
    c.post(f"/proposals/{pid}/approve", headers=h("approver"))
    line = c.get(f"/proposals/{pid}", headers=h("viewer")).json()["lines"][0]
    w = c.post(f"/proposals/{pid}/orders/{sid}/confirm", json={"lines": [{"variant_id": 1, "qty": line["qty"], "cost_with_recargo": "1.20"}]}, headers=h("buyer")).json()["cost_writes"][0]
    assert [x["id"] for x in c.get("/cost-writes", headers=h("viewer")).json()] == [w["id"]]
    assert c.get(f"/internal/cost-writes/{w['id']}", headers=h("writer")).status_code == 404                              # not released: the writer sees nothing
    assert c.get(f"/internal/cost-writes/{w['id']}", headers=h("buyer")).status_code == 403
    assert c.post(f"/cost-writes/{w['id']}/approve", headers=h("viewer")).status_code == 403
    rel = c.post(f"/cost-writes/{w['id']}/approve", headers=h("buyer"))
    assert rel.status_code == 202 and rel.json()["status"] == "approved_by_buyer"
    view = c.get(f"/internal/cost-writes/{w['id']}", headers=h("writer")).json()
    assert view["cents"] == 120 and view["previous_cents"] == 100 and view["supplier_contact_id"] == 1
    assert c.post(f"/cost-writes/{w['id']}/cancel", headers=h("buyer")).status_code == 204
    assert c.get(f"/internal/cost-writes/{w['id']}", headers=h("writer")).status_code == 404
