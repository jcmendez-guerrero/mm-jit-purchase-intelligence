"""Helpers shared by the BFF tests."""

from auth.session import COOKIE_NAME, create_session, sign_session


def headers_for(user_id: str, roles: list[str], mfa_age_seconds: int = 0) -> dict[str, str]:
    from datetime import UTC, datetime, timedelta

    sess = create_session(user_id=user_id, email=f"{user_id}@example.invalid", roles=roles, mfa_auth_time=datetime.now(UTC) - timedelta(seconds=mfa_age_seconds))
    return {"Cookie": f"{COOKIE_NAME}={sign_session(sess)}", "X-CSRF-Token": sess.csrf_token}


def admin_headers() -> dict[str, str]:
    return headers_for("admin-1", ["viewer", "admin"])


def api(method: str, path: str, headers: dict[str, str], fc=None, inv=None, **kw):
    """One request against the real app with the downstream clients replaced by mocks (feature 010 admin routes)."""
    from unittest.mock import AsyncMock

    from fastapi.testclient import TestClient
    from main import app
    from routes.api import get_inventory_client
    from routes.policies import get_forecast_client

    fc = fc or AsyncMock()
    inv = inv or AsyncMock()
    app.dependency_overrides[get_forecast_client] = lambda: fc
    app.dependency_overrides[get_inventory_client] = lambda: inv
    try:
        return TestClient(app).request(method, path, headers=headers, **kw)
    finally:
        app.dependency_overrides.clear()


def forward_by_path(table: dict[str, object]):
    """An AsyncMock whose .forward(method, path, ...) answers from a path table; unknown paths fail like an unreachable service."""
    from unittest.mock import AsyncMock

    import httpx

    async def forward(method, path, **_):
        if path in table:
            return table[path]
        raise httpx.ConnectError("down")

    m = AsyncMock()
    m.forward.side_effect = forward
    return m
