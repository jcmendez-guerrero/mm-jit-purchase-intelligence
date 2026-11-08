"""Entra ID sign-in (R12): code flow with PKCE, id_token validation, roles and MFA time. Synthetic key, no network."""

import time
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from auth import entra
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TENANT, CLIENT = "00000000-0000-0000-0000-000000000000", "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("MMI_ENV", "dev")
    monkeypatch.delenv("MMI_ENABLE_DEV_LOGIN", raising=False)
    monkeypatch.setenv("MMI_ENTRA_TENANT_ID", TENANT)
    monkeypatch.setenv("MMI_ENTRA_CLIENT_ID", CLIENT)
    monkeypatch.setenv("MMI_ENTRA_CLIENT_SECRET", "synthetic-not-a-secret")
    monkeypatch.setenv("MMI_ENTRA_REDIRECT_URI", "https://mmi.example.invalid/api/auth/callback")
    monkeypatch.setattr(entra, "signing_key", lambda cfg, token: KEY.public_key())


def client() -> TestClient:
    from main import app

    return TestClient(app, follow_redirects=False)


def id_token(nonce, **over):
    now = int(time.time())
    claims = {"iss": f"https://login.microsoftonline.com/{TENANT}/v2.0", "aud": CLIENT, "iat": now, "exp": now + 600, "nonce": nonce,
              "oid": "oid-synthetic-1", "preferred_username": "user@example.invalid", "roles": ["buyer", "bogus"], **over}
    return jwt.encode(claims, KEY, algorithm="RS256")


def start(c):
    res = c.get("/api/auth/login")
    assert res.status_code == 303
    q = parse_qs(urlparse(res.headers["location"]).query)
    assert q["code_challenge_method"] == ["S256"] and q["client_id"] == [CLIENT]
    cookie = c.cookies.get(entra.STATE_COOKIE)
    saved = entra._unsign(cookie)
    return q["state"][0], saved["n"]


def test_config_reports_the_mode(env, monkeypatch):
    assert client().get("/api/auth/config").json() == {"mode": "entra"}
    monkeypatch.setenv("MMI_ENABLE_DEV_LOGIN", "1")
    assert client().get("/api/auth/config").json() == {"mode": "dev"}
    monkeypatch.delenv("MMI_ENABLE_DEV_LOGIN")
    monkeypatch.delenv("MMI_ENTRA_CLIENT_ID")
    assert client().get("/api/auth/config").json() == {"mode": "none"}


def test_entra_routes_are_absent_in_dev_mode(env, monkeypatch):
    monkeypatch.setenv("MMI_ENABLE_DEV_LOGIN", "1")
    assert client().get("/api/auth/login").status_code == 404


def test_successful_sign_in_issues_a_session_with_token_roles(env, monkeypatch):
    c = client()
    state, nonce = start(c)
    monkeypatch.setattr(entra, "exchange_code", lambda cfg, code, verifier: id_token(nonce))
    res = c.get("/api/auth/callback", params={"code": "c", "state": state})
    assert res.status_code == 303 and res.headers["location"] == "/"
    me = c.get("/api/me").json()
    assert me["user_id"] == "oid-synthetic-1" and me["roles"] == ["buyer"]
    assert me["mfa_auth_time"].startswith("1970")          # no MFA evidence: step-up must refuse approvals


def test_mfa_time_comes_from_auth_time(env, monkeypatch):
    c = client()
    state, nonce = start(c)
    monkeypatch.setattr(entra, "exchange_code", lambda cfg, code, verifier: id_token(nonce, auth_time=int(time.time()) - 30))
    c.get("/api/auth/callback", params={"code": "c", "state": state})
    assert c.get("/api/me").json()["mfa_auth_time"].startswith("20")


@pytest.mark.parametrize("why", ["state", "nonce", "audience", "expired"])
def test_bad_sign_ins_are_refused_without_a_session(env, monkeypatch, why):
    c = client()
    state, nonce = start(c)
    over = {"audience": {"aud": "someone-else"}, "expired": {"exp": int(time.time()) - 5}}.get(why, {})
    token = id_token("wrong" if why == "nonce" else nonce, **over)
    monkeypatch.setattr(entra, "exchange_code", lambda cfg, code, verifier: token)
    res = c.get("/api/auth/callback", params={"code": "c", "state": "forged" if why == "state" else state})
    assert res.status_code == 303 and res.headers["location"].startswith("/?login_error=")
    assert c.get("/api/me").status_code == 401


def test_a_provider_error_returns_to_the_login_page(env):
    res = client().get("/api/auth/callback", params={"error": "access_denied"})
    assert res.headers["location"] == "/?login_error=denied"
