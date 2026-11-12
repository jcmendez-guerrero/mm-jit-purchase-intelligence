"""T017 (FR-008, FR-021): every sensitive admin action refuses a stale or absent second factor, audits the refusal and does nothing."""

from unittest.mock import AsyncMock

import pytest
from routes.admin_roles import get_store
from tests_support import admin_headers, api, headers_for

JOB = "5ba24d0e-5860-4dc0-baf2-caf0cb702742"
ACTIONS = [
    ("PUT", "/api/admin/roles/buyer-1", {"json": {"roles": ["viewer", "buyer"]}}),
    ("POST", "/api/admin/roles/mirror/retry", {}),
    ("POST", "/api/admin/rerun/forecast", {}),
    ("POST", f"/api/admin/rerun/import/{JOB}", {}),
    ("POST", "/api/admin/rerun/mirror", {}),
    ("PUT", "/api/admin/ops/settings", {"json": {"source_stale_hours": 48}}),
    ("POST", "/api/admin/alerts/1/acknowledge", {}),
    ("GET", "/api/admin/audit/export", {}),
    ("POST", "/api/admin/ops/queue/mirror/1/retry", {}),
]


@pytest.mark.parametrize(("method", "path", "kw"), ACTIONS)
def test_a_stale_second_factor_is_refused_audited_and_nothing_runs(method, path, kw):
    fc = AsyncMock()
    res = api(method, path, headers_for("admin-1", ["viewer", "admin"], mfa_age_seconds=301), fc=fc, **kw)
    assert res.status_code == 403 and res.json() == {"detail": "auth_mfa_stale"}
    fc.forward.assert_not_called()
    assert any(r["action"] == "access.refused" and r["actor"] == "admin-1" for r in get_store().audit_view())
    assert get_store().get("buyer-1").roles == ("buyer", "viewer")      # no side effect


@pytest.mark.parametrize(("method", "path", "kw"), ACTIONS)
def test_a_fresh_second_factor_gets_past_the_guard(method, path, kw):
    fc = AsyncMock()
    fc.forward.return_value = {"reused": True}
    res = api(method, path, admin_headers(), fc=fc, **kw)
    assert res.status_code != 403 or res.json() != {"detail": "auth_mfa_stale"}


@pytest.mark.parametrize(("method", "path", "kw"), ACTIONS)
def test_a_non_admin_is_refused_by_role_first(method, path, kw):
    res = api(method, path, headers_for("buyer-1", ["viewer", "buyer"], mfa_age_seconds=1), **kw)
    assert res.status_code == 403 and res.json() == {"detail": "auth_forbidden_role"}


def test_a_session_without_any_mfa_time_is_refused():
    from datetime import UTC, datetime

    from auth.session import COOKIE_NAME, create_session, sign_session

    # the login route stores a missing second factor as the epoch (routes/api.py)
    sess = create_session(user_id="admin-1", email="a@example.invalid", roles=["viewer", "admin"], mfa_auth_time=datetime(1970, 1, 1, tzinfo=UTC))
    res = api("POST", "/api/admin/rerun/mirror", {"Cookie": f"{COOKIE_NAME}={sign_session(sess)}", "X-CSRF-Token": sess.csrf_token})
    assert res.status_code == 403 and res.json() == {"detail": "auth_mfa_stale"}
