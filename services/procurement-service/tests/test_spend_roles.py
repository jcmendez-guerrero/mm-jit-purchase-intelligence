"""T100 (feature 006, FR-017/FR-026): /summary/spend returns money, so the service itself refuses a role without cost access; the gateway is not the only guard."""

import pytest
from api import costs, summary
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app

ROLES = {"viewer": {"viewer"}, "buyer": {"buyer"}, "approver": {"approver"}, "admin": {"admin"}}


class V:
    def validate(self, token, required_roles=()):
        if token not in ROLES:
            raise AuthError("unauthorized", 401)
        return Principal("u", frozenset(ROLES[token]), None)


def get(engine, role):
    app = create_service_app("procurement-service", validator=V())
    app.include_router(costs.build_router(app))
    app.include_router(summary.build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app).get("/summary/spend?date_from=2026-10-26&date_to=2026-11-09", headers={"Authorization": f"Bearer {role}"})


def test_a_viewer_gets_no_money_from_the_service(engine):
    r = get(engine, "viewer")
    assert r.status_code == 403 and "open_orders" not in r.text and "range" not in r.text


@pytest.mark.parametrize("role", ["buyer", "approver", "admin"])
def test_the_cost_roles_still_get_the_summary(engine, role):
    r = get(engine, role)
    assert r.status_code == 200 and {"open_orders", "range"} <= r.json().keys()
