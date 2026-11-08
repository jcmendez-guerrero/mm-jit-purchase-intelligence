"""T026: roles survive a restart; the last admin cannot be removed; two approvers are required but can always be reached."""

import pytest
from db.engine import make_engine
from db.roles import RoleError, RoleStore
from fastapi.testclient import TestClient
from tests_support import admin_headers


def test_roles_persist_across_a_restart(tmp_path):
    url = f"sqlite:///{tmp_path / 'bff.db'}"
    first = RoleStore(make_engine(url))
    first.replace_all({"admin-1": ["viewer", "admin"], "approver-1": ["viewer", "approver"], "approver-2": ["viewer", "approver"]})
    first.set_roles("buyer-9", ["viewer", "buyer"], actor="admin-1")
    restarted = RoleStore(make_engine(url))            # a new process with the same database
    rec = restarted.get("buyer-9")
    assert rec is not None and list(rec.roles) == ["buyer", "viewer"] and rec.revision == 1
    assert restarted.approver_count() == 2
    assert restarted.verify_audit().ok


def test_api_changes_are_visible_after_a_restart(role_store, tmp_path):
    from main import app
    from routes import admin_roles

    url = f"sqlite:///{tmp_path / 'api.db'}"
    store = RoleStore(make_engine(url))
    store.replace_all({"admin-1": ["viewer", "admin"], "approver-1": ["viewer", "approver"], "approver-2": ["viewer", "approver"]})
    admin_roles.set_store(store)
    res = TestClient(app).put("/api/admin/roles/buyer-5", json={"roles": ["viewer", "buyer"]}, headers=admin_headers())
    assert res.status_code == 200
    admin_roles.set_store(RoleStore(make_engine(url)))   # restart
    listing = TestClient(app).get("/api/admin/roles", headers=admin_headers()).json()
    assert {"user_id": "buyer-5", "roles": ["buyer", "viewer"]} in [{k: u[k] for k in ("user_id", "roles")} for u in listing["users"]]


def test_the_last_admin_cannot_be_removed(role_store):
    with pytest.raises(RoleError) as exc:
        role_store.set_roles("admin-1", ["viewer"], actor="admin-1")
    assert exc.value.code == "roles_last_admin"
    assert "admin" in role_store.get("admin-1").roles


def test_a_second_admin_makes_removal_possible(role_store):
    role_store.set_roles("buyer-1", ["viewer", "admin"], actor="admin-1")
    role_store.set_roles("admin-1", ["viewer"], actor="buyer-1")
    assert "admin" not in role_store.get("admin-1").roles


def test_removing_an_approver_below_two_is_refused(role_store):
    with pytest.raises(RoleError) as exc:
        role_store.set_roles("approver-2", ["viewer"], actor="admin-1")
    assert exc.value.code == "approval_fewer_than_two_approvers"
    assert role_store.approver_count() == 2


def test_a_second_approver_can_always_be_added_even_with_only_one(tmp_path):
    """Regression: the previous registry refused every change while fewer than two approvers existed, so a fresh system could never reach two."""
    store = RoleStore(make_engine("sqlite://"))
    store.replace_all({"admin-1": ["viewer", "admin"], "approver-1": ["viewer", "approver"]})
    store.set_roles("buyer-1", ["viewer", "buyer", "approver"], actor="admin-1")
    assert store.approver_count() == 2


def test_invalid_roles_are_refused(role_store):
    with pytest.raises(RoleError) as exc:
        role_store.set_roles("buyer-1", ["viewer", "superuser"], actor="admin-1")
    assert exc.value.code == "roles_invalid"


def test_inactive_users_do_not_count_as_approvers(role_store):
    role_store.set_roles("buyer-1", ["viewer", "buyer", "approver"], actor="admin-1")           # three approvers
    role_store.set_roles("buyer-1", ["viewer", "buyer", "approver"], actor="admin-1", active=False)
    assert role_store.approver_count() == 2


def test_deactivating_one_of_only_two_approvers_is_refused(role_store):
    with pytest.raises(RoleError) as exc:
        role_store.set_roles("approver-2", ["viewer", "approver"], actor="admin-1", active=False)
    assert exc.value.code == "approval_fewer_than_two_approvers"


def test_every_change_is_audited_and_the_chain_verifies(role_store):
    role_store.set_roles("buyer-1", ["viewer", "buyer", "approver"], actor="admin-1")
    events = role_store.audit_view()
    assert events[-1]["actor"] == "admin-1" and events[-1]["target_user"] == "buyer-1" and events[-1]["success"] is True
    assert role_store.verify_audit().ok
