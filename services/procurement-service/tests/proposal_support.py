"""Shared fixtures for the proposal-domain guarantee tests (feature 011): the proposal routes on an in-memory database with one synthetic supplier.

Import with ``from proposal_support import api, generate, h  # noqa: F401, F811``.
"""

from __future__ import annotations

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
         "admin": {"viewer", "admin"}, "viewer": {"viewer"}, "stale": {"viewer", "approver"}}


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

    def build(self, conn, today):
        return inputs([variant(1, [offer(self.supplier, "1.00", pack=6)], flat_forecast(1.0))], [terms(self.supplier)], budget="1000")


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


def generate(client, role="buyer"):
    r = client.post("/proposals", headers=h(role))
    assert r.status_code == 202
    return r.json()["id"]


def approve_flow(client, pid):
    assert client.post(f"/proposals/{pid}/submit", headers=h("buyer")).status_code == 200
    assert client.post(f"/proposals/{pid}/approve", headers=h("approver")).status_code == 200
