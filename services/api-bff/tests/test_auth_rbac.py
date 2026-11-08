"""Tests for T109, T110, T111: BFF auth, cookie session, CSRF, step-up MFA, RBAC and aggregation routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from auth.session import COOKIE_NAME, create_session, sign_session
from fastapi.testclient import TestClient
from main import app
from routes.api import get_inventory_client, get_procurement_client
from routes.rbac import clear_refusal_log, get_refusal_log


def test_auth_dev_login_sets_cookie_and_returns_me(monkeypatch):
    monkeypatch.setenv("MMI_ENV", "dev")
    monkeypatch.setenv("MMI_ENABLE_DEV_LOGIN", "1")
    client = TestClient(app)
    # Dev login sets cookie
    res = client.post("/api/auth/dev-login", json={"user_id": "buyer-1", "roles": ["viewer", "buyer"]})
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "buyer-1"
    assert "csrf_token" in data
    assert COOKIE_NAME in res.cookies

    # Access /api/me with cookie
    res_me = client.get("/api/me", cookies=res.cookies)
    assert res_me.status_code == 200
    assert res_me.json()["user_id"] == "buyer-1"

    # Logout clears cookie
    res_logout = client.post("/api/auth/logout", cookies=res.cookies, headers={"X-CSRF-Token": data["csrf_token"]})
    assert res_logout.status_code == 200


def test_csrf_protection_on_mutating_requests():
    client = TestClient(app)
    sess = create_session("buyer-1", "buyer@example.com", ["viewer", "buyer"])
    cookies = {COOKIE_NAME: sign_session(sess)}

    # Missing CSRF token on mutating request -> 403
    res = client.post("/api/auth/logout", cookies=cookies)
    assert res.status_code == 403
    assert res.json()["detail"] == "auth_csrf_invalid"

    # Invalid CSRF token -> 403
    res = client.post("/api/auth/logout", cookies=cookies, headers={"X-CSRF-Token": "bad-token"})
    assert res.status_code == 403

    # Correct CSRF token -> 200
    res = client.post("/api/auth/logout", cookies=cookies, headers={"X-CSRF-Token": sess.csrf_token})
    assert res.status_code == 200


def test_rbac_viewer_can_read_but_cannot_mutate():
    client = TestClient(app)
    clear_refusal_log()
    sess = create_session("viewer-1", "viewer@example.com", ["viewer"])
    headers = {"Cookie": f"{COOKIE_NAME}={sign_session(sess)}", "X-CSRF-Token": sess.csrf_token}

    mock_proc = AsyncMock()
    mock_proc.get_proposals.return_value = [{"id": "prop-1"}]
    app.dependency_overrides[get_procurement_client] = lambda: mock_proc

    try:
        # Viewer can read proposals
        res = client.get("/api/proposals", headers=headers)
        assert res.status_code == 200

        # Viewer cannot submit proposal -> 403
        res_sub = client.post("/api/proposals/prop-1/submit", headers=headers)
        assert res_sub.status_code == 403

        # Check refusal was logged
        refusals = get_refusal_log()
        assert any(r["user_id"] == "viewer-1" and r["reason"] == "forbidden_missing_role" for r in refusals)
    finally:
        app.dependency_overrides.clear()


def test_step_up_mfa_requirement():
    client = TestClient(app)
    clear_refusal_log()

    # Approver with stale MFA (10 minutes ago)
    stale_time = datetime.now(UTC) - timedelta(minutes=10)
    stale_sess = create_session("approver-1", "approver@example.com", ["viewer", "approver"], mfa_auth_time=stale_time)
    stale_headers = {"Cookie": f"{COOKIE_NAME}={sign_session(stale_sess)}", "X-CSRF-Token": stale_sess.csrf_token}

    # Approving proposal with stale MFA -> 403 fresh MFA required
    res = client.post("/api/proposals/prop-1/approve", headers=stale_headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "auth_mfa_stale"

    # Approver with fresh MFA (1 minute ago)
    fresh_sess = create_session("approver-1", "approver@example.com", ["viewer", "approver"], mfa_auth_time=datetime.now(UTC) - timedelta(minutes=1))
    fresh_headers = {"Cookie": f"{COOKIE_NAME}={sign_session(fresh_sess)}", "X-CSRF-Token": fresh_sess.csrf_token}

    mock_proc = AsyncMock()
    mock_proc.approve_proposal.return_value = {"id": "prop-1", "status": "approved"}
    app.dependency_overrides[get_procurement_client] = lambda: mock_proc

    try:
        res_ok = client.post("/api/proposals/prop-1/approve", headers=fresh_headers)
        assert res_ok.status_code == 200
        assert res_ok.json()["status"] == "approved"
    finally:
        app.dependency_overrides.clear()


def test_bff_aggregation_routes():
    client = TestClient(app)
    sess = create_session("buyer-1", "buyer@example.com", ["viewer", "buyer"])
    headers = {"Cookie": f"{COOKIE_NAME}={sign_session(sess)}", "X-CSRF-Token": sess.csrf_token}

    mock_inv = AsyncMock()
    mock_inv.get_risks.return_value = [{"variant_id": 1, "risk_type": "stockout", "explanation_key": "risk.stockout.imminent"}]
    mock_inv.get_variant_detail.return_value = {"variant": {"id": 1, "sku": "AMX-500"}}
    mock_inv.get_review_items.return_value = {"count": 1, "items": [{"id": 10}]}
    app.dependency_overrides[get_inventory_client] = lambda: mock_inv

    try:
        # Dashboard risk
        res = client.get("/api/dashboard/risk", headers=headers)
        assert res.status_code == 200
        assert len(res.json()) == 1

        # Variant detail
        res = client.get("/api/inventory/variants/1", headers=headers)
        assert res.status_code == 200
        assert res.json()["variant"]["sku"] == "AMX-500"

        # Data quality review
        res = client.get("/api/data-quality/import-errors", headers=headers)
        assert res.status_code == 200
        assert res.json()["count"] == 1
    finally:
        app.dependency_overrides.clear()
