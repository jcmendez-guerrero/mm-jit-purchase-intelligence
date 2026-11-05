"""Tests for T137: admin role assignment/revocation, audit logging, and the two-approver rule."""

from auth.session import COOKIE_NAME, create_session, sign_session
from fastapi.testclient import TestClient
from routes.admin_roles import clear_audit_log, get_audit_log, set_initial_users


def make_client():
    from main import app
    return TestClient(app)


def cookie_header(user_id: str, roles: list[str]) -> tuple[dict[str, str], str]:
    sess = create_session(user_id=user_id, email=f"{user_id}@example.com", roles=roles)
    cookie_str = f"{COOKIE_NAME}={sign_session(sess)}"
    headers = {"Cookie": cookie_str, "X-CSRF-Token": sess.csrf_token}
    return headers, sess.csrf_token


def test_non_admin_cannot_access_roles():
    client = make_client()
    clear_audit_log()
    headers, _ = cookie_header("buyer-1", ["viewer", "buyer"])

    # Non-admin viewing roles gets 403
    res = client.get("/api/admin/roles", headers=headers)
    assert res.status_code == 403

    # Non-admin updating roles gets 403
    res = client.put("/api/admin/roles/approver-1", json={"roles": ["viewer"]}, headers=headers)
    assert res.status_code == 403


def test_admin_can_view_and_update_roles():
    client = make_client()
    clear_audit_log()
    set_initial_users({
        "buyer-1": ["viewer", "buyer"],
        "approver-1": ["viewer", "approver"],
        "approver-2": ["viewer", "approver"],
        "approver-3": ["viewer", "approver"],
        "admin-1": ["viewer", "admin"],
    })

    headers, _ = cookie_header("admin-1", ["viewer", "admin"])

    # Admin lists roles
    res = client.get("/api/admin/roles", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["eligible_approvers_count"] == 3

    # Admin updates approver-3 to viewer only (still leaves 2 approvers: approver-1, approver-2)
    res = client.put("/api/admin/roles/approver-3", json={"roles": ["viewer"]}, headers=headers)
    assert res.status_code == 200
    assert res.json()["roles"] == ["viewer"]

    audit = get_audit_log()
    assert len(audit) == 1
    assert audit[0]["actor"] == "admin-1"
    assert audit[0]["target_user"] == "approver-3"
    assert audit[0]["success"] is True


def test_admin_cannot_leave_fewer_than_two_approvers():
    client = make_client()
    clear_audit_log()
    set_initial_users({
        "buyer-1": ["viewer", "buyer"],
        "approver-1": ["viewer", "approver"],
        "approver-2": ["viewer", "approver"],
        "admin-1": ["viewer", "admin"],
    })

    headers, _ = cookie_header("admin-1", ["viewer", "admin"])

    # With only 2 approvers, revoking approver role from approver-2 must fail with 409
    res = client.put("/api/admin/roles/approver-2", json={"roles": ["viewer"]}, headers=headers)
    assert res.status_code == 409
    assert "at least two eligible approvers" in res.json()["detail"]

    # Check refused attempt is logged
    audit = get_audit_log()
    assert len(audit) == 1
    assert audit[0]["actor"] == "admin-1"
    assert audit[0]["target_user"] == "approver-2"
    assert audit[0]["success"] is False
    assert "at least two" in (audit[0]["refusal_reason"] or "")
