"""T028: refused attempts are recorded durably; unauthenticated floods are not; revoked roles apply at once."""

from datetime import UTC, datetime

from db.engine import make_engine
from db.roles import RoleStore
from fastapi.testclient import TestClient
from tests_support import headers_for


def client():
    from main import app

    return TestClient(app)


def test_a_viewer_mutation_is_refused_and_recorded_in_the_audit_chain(role_store):
    res = client().put("/api/admin/roles/buyer-1", json={"roles": ["viewer"]}, headers=headers_for("buyer-1", ["viewer", "buyer"]))
    assert res.status_code == 403 and res.json()["detail"] == "auth_forbidden_role"
    refusals = [e for e in role_store.audit_view() if e["action"] == "access.refused"]
    assert refusals and refusals[-1]["actor"] == "buyer-1" and "/api/admin/roles/buyer-1" in refusals[-1]["target_user"]
    assert role_store.verify_audit().ok


def test_refusals_survive_a_restart(role_store, tmp_path):
    from routes import admin_roles

    url = f"sqlite:///{tmp_path / 'r.db'}"
    store = RoleStore(make_engine(url))
    store.replace_all({"admin-1": ["viewer", "admin"], "buyer-1": ["viewer", "buyer"]})
    admin_roles.set_store(store)
    client().put("/api/admin/roles/buyer-1", json={"roles": ["viewer"]}, headers=headers_for("buyer-1", ["viewer", "buyer"]))
    assert any(e["action"] == "access.refused" for e in RoleStore(make_engine(url)).audit_view())


def test_unauthenticated_requests_get_401_without_writing_to_the_database(role_store):
    before = len(role_store.audit_view())
    for _ in range(5):
        res = client().get("/api/admin/roles")
        assert res.status_code == 401 and res.json()["detail"] == "auth_unauthenticated"
    assert len(role_store.audit_view()) == before          # a flood of anonymous calls cannot grow the audit table


def test_missing_csrf_token_is_refused_with_a_code(role_store):
    h = headers_for("admin-1", ["viewer", "admin"])
    h.pop("X-CSRF-Token")
    res = client().put("/api/admin/roles/buyer-1", json={"roles": ["viewer", "buyer"]}, headers=h)
    assert res.status_code == 403 and res.json()["detail"] == "auth_csrf_invalid"


def test_a_revoked_role_applies_even_if_the_session_cookie_still_carries_it(role_store):
    """The cookie was issued when the user was an admin; the registry now says viewer, and the registry wins."""
    role_store.set_roles("buyer-1", ["viewer", "admin"], actor="admin-1")
    h = headers_for("buyer-1", ["viewer", "admin"])
    assert client().get("/api/admin/roles", headers=h).status_code == 200
    role_store.set_roles("buyer-1", ["viewer"], actor="admin-1")
    res = client().get("/api/admin/roles", headers=h)
    assert res.status_code == 403 and res.json()["detail"] == "auth_forbidden_role"


def test_a_deactivated_user_is_refused_everywhere(role_store):
    role_store.set_roles("buyer-1", ["viewer", "buyer"], actor="admin-1", active=False)
    assert client().get("/api/me", headers=headers_for("buyer-1", ["viewer", "buyer"])).status_code == 403


def test_users_unknown_to_the_registry_keep_their_session_roles(role_store):
    res = client().get("/api/me", headers=headers_for("entra-user-7", ["viewer"]))
    assert res.status_code == 200 and res.json()["roles"] == ["viewer"]
    assert datetime.now(UTC)
