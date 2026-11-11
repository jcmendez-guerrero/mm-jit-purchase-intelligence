"""Feature 011 (T054): always-stocked, safety-stock override and recommendation routes take the SKU; a raw ERP id is refused and answers carry the SKU."""

from datetime import UTC, datetime, timedelta

import pytest
from api import costs, policies
from db.tables import product_refs
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from sqlalchemy import insert

ROLES = {"buyer": {"viewer", "buyer"}, "approver": {"viewer", "approver"}, "viewer": {"viewer"}}


class V:
    def validate(self, token, required_roles=()):
        roles = ROLES.get(token)
        if roles is None or not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(f"user-{token}", frozenset(roles), datetime.now(UTC) - timedelta(minutes=1))


def h(role, **extra):
    return {"Authorization": f"Bearer {role}", **extra}


@pytest.fixture
def api(engine, monkeypatch):
    with engine.begin() as c:
        c.execute(insert(product_refs).values(variant_id=5, product_id=5, sku="SYN-0005", name="Producto sintético"))
        c.execute(insert(product_refs).values(variant_id=6, product_id=6, sku="dup", name="A"))
        c.execute(insert(product_refs).values(variant_id=7, product_id=7, sku="DUP ", name="B"))
    monkeypatch.setattr(policies, "recommended_safety_stock", lambda c, v: 5)
    app = create_service_app("procurement-service", validator=V())
    app.include_router(costs.build_router(app))
    app.include_router(policies.build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app)


def test_stocking_is_read_and_saved_by_sku(api):
    assert api.get("/stocking/syn-0005", headers=h("viewer")).json()["sku"] == "SYN-0005"
    assert api.put("/stocking/SYN-0005", json={"stocking_mode": "always_stocked", "min_floor_units": 2}, headers=h("buyer")).json() == {"revision": 1}
    got = api.get("/stocking/SYN-0005", headers=h("viewer")).json()
    assert got["stocking_mode"] == "always_stocked" and got["sku"] == "SYN-0005" and got["revision"] == 1
    assert api.put("/stocking/SYN-0005", json={"stocking_mode": "standard", "min_floor_units": 0}, headers=h("buyer")).status_code == 428


@pytest.mark.parametrize("sku", ["5", "NOPE"])
def test_a_raw_id_or_an_unknown_sku_is_refused_on_every_route(api, sku):
    assert api.get(f"/stocking/{sku}", headers=h("viewer")).json()["detail"] == "sku_unknown"
    assert api.put(f"/stocking/{sku}", json={"stocking_mode": "standard", "min_floor_units": 0}, headers=h("buyer")).json()["detail"] == "sku_unknown"
    assert api.get(f"/policy-overrides/recommendation/{sku}", headers=h("viewer")).json()["detail"] == "sku_unknown"
    assert api.post("/policy-overrides", json={"sku": sku, "field": "min", "requested_value": 3, "reason": "campaña"}, headers=h("buyer")).json()["detail"] == "sku_unknown"


def test_an_ambiguous_sku_is_refused(api):
    assert api.get("/stocking/DUP", headers=h("viewer")).json()["detail"] == "sku_ambiguous"


def test_an_override_is_requested_and_listed_by_sku(api):
    created = api.post("/policy-overrides", json={"sku": "SYN-0005", "field": "safety_stock", "requested_value": 9, "reason": "proveedor poco fiable"}, headers=h("buyer"))
    assert created.status_code == 201 and created.json()["sku"] == "SYN-0005" and created.json()["recommended_value"] == 5
    listed = api.get("/policy-overrides", headers=h("viewer")).json()
    assert [r["sku"] for r in listed] == ["SYN-0005"]


def test_the_recommendation_is_read_by_sku(api):
    body = api.get("/policy-overrides/recommendation/syn-0005", headers=h("viewer")).json()
    assert body["sku"] == "SYN-0005" and body["safety_stock"] == 5
