"""A business refusal from a downstream service (self-approval, stale version, ...) reaches the user as the same status and stable
code, not as a 500; outages become a 502/503 with a code and never leak the downstream body."""

from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient
from routes.api import get_procurement_client
from tests_support import headers_for


def downstream(status: int, body: dict | str) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "http://procurement/proposals/p1/approve")
    res = httpx.Response(status, request=req, json=body) if isinstance(body, dict) else httpx.Response(status, request=req, text=body)
    return httpx.HTTPStatusError("x", request=req, response=res)


def call(exc: Exception):
    from main import app

    mock = AsyncMock()
    mock.approve_proposal.side_effect = exc
    app.dependency_overrides[get_procurement_client] = lambda: mock
    try:
        return TestClient(app).post("/api/proposals/p1/approve", headers=headers_for("approver-1", ["viewer", "approver"]))
    finally:
        app.dependency_overrides.clear()


def test_a_business_refusal_keeps_its_status_and_code():
    res = call(downstream(403, {"detail": "creator_cannot_approve"}))
    assert res.status_code == 403 and res.json() == {"detail": "creator_cannot_approve"}


def test_a_version_conflict_keeps_409():
    assert call(downstream(409, {"detail": "version_conflict"})).status_code == 409


def test_free_text_or_html_from_downstream_is_never_passed_through():
    res = call(downstream(403, {"detail": "Traceback (most recent call last): secret path /srv/x"}))
    assert res.status_code == 403 and res.json() == {"detail": "downstream_refused"}
    assert call(downstream(400, "<html>boom</html>")).json() == {"detail": "downstream_refused"}


def test_a_downstream_server_error_is_a_502_with_a_code():
    res = call(downstream(500, {"detail": "database exploded at 10.0.0.5"}))
    assert res.status_code == 502 and res.json() == {"detail": "downstream_unavailable"}


def test_an_unreachable_service_is_a_502():
    assert call(httpx.ConnectError("refused")).json() == {"detail": "downstream_unavailable"}


def test_a_missing_identity_configuration_is_a_503():
    res = call(RuntimeError("no identity issuer configured for downstream calls"))
    assert res.status_code == 503 and res.json() == {"detail": "authentication_unavailable"}
