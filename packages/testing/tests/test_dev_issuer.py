"""The dev issuer can issue end-user tokens carrying the user's real second-factor time, and still refuses service impersonation."""

from datetime import UTC, datetime, timedelta

import jwt
from dev_issuer import create_app
from fastapi.testclient import TestClient


def client(monkeypatch):
    monkeypatch.setenv("MMI_ENV", "dev")
    return TestClient(create_app())


def decode(token):
    return jwt.decode(token, options={"verify_signature": False})


def test_user_tokens_carry_the_user_roles_and_second_factor_time(monkeypatch):
    c = client(monkeypatch)
    t = int((datetime.now(UTC) - timedelta(minutes=9)).timestamp())
    r = c.post("/token", json={"subject": "approver-2", "audience": "api://x", "roles": ["viewer", "approver"], "user": True, "auth_time": t})
    claims = decode(r.json()["access_token"])
    assert claims["sub"] == "approver-2" and claims["roles"] == ["viewer", "approver"] and claims["auth_time"] == t


def test_a_user_token_can_never_look_like_a_service(monkeypatch):
    c = client(monkeypatch)
    for subject in ("svc-api-bff", "dev-anything", "../etc", "a b", ""):
        assert c.post("/token", json={"subject": subject, "audience": "api://x", "user": True}).status_code == 422


def test_service_tokens_keep_their_prefix_rule(monkeypatch):
    c = client(monkeypatch)
    assert c.post("/token", json={"subject": "svc-api-bff", "audience": "api://x", "roles": ["bff"]}).status_code == 200
    assert c.post("/token", json={"subject": "buyer-1", "audience": "api://x"}).status_code == 422
