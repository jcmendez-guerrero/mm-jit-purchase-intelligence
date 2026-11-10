"""T010, T011: every role-change guard keeps its stable code, a stale edit is a conflict, unknown claim roles are ignored."""

from auth.entra import identity_from_claims
from routes.admin_roles import get_store
from tests_support import admin_headers, api, headers_for


def put(user, body, headers=None):
    return api("PUT", f"/api/admin/roles/{user}", headers or admin_headers(), json=body)


def test_each_guard_returns_its_stable_code():
    assert put("buyer-1", {"roles": ["viewer", "superuser"]}).json() == {"detail": "roles_invalid"}
    last_admin = put("admin-1", {"roles": ["viewer"]})
    assert last_admin.status_code == 409 and last_admin.json() == {"detail": "roles_last_admin"}
    fewer = put("approver-1", {"roles": ["viewer"]})
    assert fewer.status_code == 409 and fewer.json() == {"detail": "approval_fewer_than_two_approvers"}
    refusals = [r for r in get_store().audit_view() if r["action"] == "roles.refused"]
    assert {r["refusal_reason"] for r in refusals} == {"roles_invalid", "roles_last_admin", "approval_fewer_than_two_approvers"}


def test_unknown_claim_roles_are_ignored_and_a_person_without_roles_gets_least_privilege():
    _, _, roles, _ = identity_from_claims({"oid": "u1", "roles": ["admin", "root", "godmode"]})
    assert roles == ["admin"]
    assert api("GET", "/api/admin/roles", headers_for("nobody", [])).status_code == 403


def test_a_stale_expected_revision_is_a_conflict_and_a_missing_one_keeps_today_behaviour():
    first = put("buyer-7", {"roles": ["viewer", "buyer"]})
    assert first.status_code == 200 and first.json()["revision"] == 1
    stale = put("buyer-7", {"roles": ["viewer"], "expected_revision": 0})
    assert stale.status_code == 409 and stale.json() == {"detail": "roles_conflict"}
    assert get_store().get("buyer-7").revision == 1                      # nothing changed
    ok = put("buyer-7", {"roles": ["viewer"], "expected_revision": 1})
    assert ok.status_code == 200 and ok.json()["revision"] == 2
    assert put("buyer-7", {"roles": ["viewer", "buyer"]}).json()["revision"] == 3
    assert any(r["action"] == "roles.refused" and r["refusal_reason"] == "roles_conflict" for r in get_store().audit_view())


def test_a_new_user_needs_expected_revision_zero():
    assert put("fresh-1", {"roles": ["viewer"], "expected_revision": 0}).status_code == 200
    assert put("fresh-2", {"roles": ["viewer"], "expected_revision": 3}).json() == {"detail": "roles_conflict"}
