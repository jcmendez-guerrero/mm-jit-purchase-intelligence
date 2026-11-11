"""Feature 011 (T057): forecast parameter changes appear in the admin audit read, with the previous value, and nothing else."""

import pytest
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app

ROLES = {"buyer": {"viewer", "buyer"}, "admin": {"viewer", "buyer", "approver", "admin"}}


class V:
    def validate(self, token, required_roles=()):
        roles = ROLES.get(token, {"viewer"})
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(f"user-{token}", frozenset(roles), None)


@pytest.fixture
def api(engine):
    from api import build_router, get_engine

    app = create_service_app("forecast-service", validator=V())
    app.include_router(build_router(app))
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app)


def h(role, **extra):
    return {"Authorization": f"Bearer {role}", **extra}


def test_the_audit_read_is_admin_only_and_shows_the_previous_value(api):
    api.put("/parameters/lead_time", json={"value": "9"}, headers=h("buyer"))
    api.put("/parameters/lead_time", json={"value": "12"}, headers=h("buyer", **{"If-Match": '"1"'}))
    assert api.get("/policy-audit", headers=h("buyer")).status_code == 403
    items = api.get("/policy-audit", headers=h("admin")).json()["items"]
    assert [i["action"] for i in items] == ["parameter.saved", "parameter.saved"]          # newest first
    newest, oldest = items
    assert oldest["before"] is None and oldest["after"]["value"] == "9"
    assert newest["before"]["value"] == "9" and newest["before"]["revision"] == 1 and newest["after"]["value"] == "12" and newest["entity_id"] == "lead_time"
    assert newest["actor"] == "user-buyer" and newest["outcome"] == "accepted"
