"""Helpers shared by the BFF tests."""

from auth.session import COOKIE_NAME, create_session, sign_session


def headers_for(user_id: str, roles: list[str], mfa_age_seconds: int = 0) -> dict[str, str]:
    from datetime import UTC, datetime, timedelta

    sess = create_session(user_id=user_id, email=f"{user_id}@example.invalid", roles=roles, mfa_auth_time=datetime.now(UTC) - timedelta(seconds=mfa_age_seconds))
    return {"Cookie": f"{COOKIE_NAME}={sign_session(sess)}", "X-CSRF-Token": sess.csrf_token}


def admin_headers() -> dict[str, str]:
    return headers_for("admin-1", ["viewer", "admin"])
