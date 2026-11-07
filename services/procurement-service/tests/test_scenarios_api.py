"""The scenario routes: roles, Idempotency-Key, promotion and export over HTTP."""

from datetime import UTC, datetime, timedelta

import pytest
from api import costs, scenarios
from conftest import add_supplier
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from scen import Blob, base

ROLES = {"buyer": {"viewer", "buyer"}, "viewer": {"viewer"}}


class V:
    def validate(self, token, required_roles=()):
        roles = ROLES.get(token)
        if roles is None or not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(f"user-{token}", frozenset(roles), datetime.now(UTC) - timedelta(minutes=1))


class Provider:
    def __init__(self, sa, sb):
        self.sa, self.sb = sa, sb

    def build(self, conn, today):
        return base(self.sa, self.sb)


def h(role="buyer", **extra):
    return {"Authorization": f"Bearer {role}", **extra}


@pytest.fixture
def api(engine, tmp_path):
    with engine.begin() as c:
        sa, sb = add_supplier(c, 1, "Proveedor A"), add_supplier(c, 2, "Proveedor B")
    app = create_service_app("procurement-service", validator=V())
    app.include_router(costs.build_router(app))
    app.include_router(scenarios.build_router(app))
    app.state.inputs_provider, app.state.blob_writer = Provider(sa, sb), Blob(tmp_path)
    app.dependency_overrides[costs.get_engine] = lambda: engine
    c = TestClient(app)
    c.sa = sa
    return c


def body(sa):
    return {"name": "Sin A", "disabled_suppliers": [sa]}


def test_creating_needs_the_buyer_role_and_an_idempotency_key_and_validates_the_input(api):
    assert api.post("/scenarios", json=body(api.sa), headers=h("viewer", **{"Idempotency-Key": "abcdefgh1"})).status_code == 403
    assert api.post("/scenarios", json=body(api.sa), headers=h()).json()["detail"] == "idempotency_key_required"
    assert api.post("/scenarios", json={"name": "x", "budget": "-5"}, headers=h(**{"Idempotency-Key": "abcdefgh2"})).status_code == 422
    assert api.post("/scenarios", json={"name": "", "disabled_suppliers": []}, headers=h(**{"Idempotency-Key": "abcdefgh3"})).status_code == 422


def test_the_same_key_returns_the_same_scenario_and_it_can_be_listed_and_read(api):
    one = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-repeat-1"}))
    two = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-repeat-1"}))
    assert one.status_code == 201 and two.json()["id"] == one.json()["id"]
    sid = one.json()["id"]
    assert api.get(f"/scenarios/{sid}", headers=h("viewer")).json()["status"] == "ready"
    assert [s["id"] for s in api.get("/scenarios", headers=h("viewer")).json()["scenarios"]] == [sid]
    assert api.get("/scenarios/nope", headers=h("viewer")).json()["detail"] == "unknown_scenario" and api.get("/scenarios").status_code == 401


def test_promotion_is_buyer_only_creates_a_draft_and_cannot_repeat(api):
    sid = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-promote-1"})).json()["id"]
    assert api.post(f"/scenarios/{sid}/promote", headers=h("viewer")).status_code == 403
    r = api.post(f"/scenarios/{sid}/promote", json={"week": "2026-W46"}, headers=h())
    assert r.status_code == 201 and r.json()["week"] == "2026-W46" and r.json()["proposal_id"]
    assert api.post(f"/scenarios/{sid}/promote", headers=h()).json()["detail"] == "scenario_already_promoted"
    assert api.post("/scenarios/nope/promote", headers=h()).status_code == 404
    assert api.post(f"/scenarios/{sid}/promote", json={"week": "x"}, headers=h()).status_code == 422


def test_export_returns_the_chosen_format_and_refuses_others(api):
    sid = api.post("/scenarios", json=body(api.sa), headers=h(**{"Idempotency-Key": "key-export-1"})).json()["id"]
    csv = api.get(f"/scenarios/{sid}/export?format=csv", headers=h("viewer"))
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv") and "escenario.csv" in csv.headers["content-disposition"]
    assert api.get(f"/scenarios/{sid}/export?format=xlsx", headers=h("viewer")).status_code == 200
    assert api.get(f"/scenarios/{sid}/export?format=pdf", headers=h("viewer")).status_code == 422
    assert api.get("/scenarios/nope/export?format=csv", headers=h("viewer")).status_code == 404
