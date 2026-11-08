"""Procurement decides separation of duties and MFA freshness from the token, so the BFF must send the real user, their
effective roles and their real MFA time - never a shared service subject, never every role, never a fresh-looking time."""

import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from auth.identity import current_identity
from auth.session import create_session
from clients import base
from clients.base import DownstreamClient, get_downstream_token


class FakeIssuer:
    """Stands in for the dev issuer: records the request and returns an unsigned token carrying the same claims."""

    def __init__(self):
        self.requests: list[dict] = []

    def post(self, url, json):
        self.requests.append(json)

        class R:
            status_code = 200

            def json(self_inner):
                return {"access_token": jwt.encode({"sub": json["subject"], "roles": json["roles"], "auth_time": json.get("auth_time")}, "k", algorithm="HS256")}

        return R()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def issuer(monkeypatch):
    fake = FakeIssuer()
    base._token_cache.clear()
    monkeypatch.delenv("MMI_TEST_SERVICE_TOKEN", raising=False)
    monkeypatch.setenv("MMI_DEV_ISSUER_URL", "http://issuer.invalid")
    monkeypatch.setattr(base.httpx, "Client", lambda **kw: fake)
    return fake


def claims(token):
    return jwt.decode(token, options={"verify_signature": False})


def test_the_user_subject_roles_and_mfa_time_reach_the_issuer(issuer):
    mfa = datetime.now(UTC) - timedelta(minutes=12)
    sess = create_session("approver-2", "a@example.invalid", ["viewer", "approver"], mfa_auth_time=mfa)
    token_ctx = current_identity.set(sess)
    try:
        c = claims(get_downstream_token("api://mmi-procurement-service", ["viewer", "approver"]))
    finally:
        current_identity.reset(token_ctx)
    assert c["sub"] == "approver-2" and sorted(c["roles"]) == ["approver", "viewer"]
    assert int(c["auth_time"]) == int(mfa.timestamp())                 # a stale second factor stays stale downstream


def test_two_users_never_share_a_cached_token(issuer):
    for uid in ("buyer-1", "approver-1"):
        tok = current_identity.set(create_session(uid, "x@example.invalid", ["viewer"]))
        try:
            assert claims(get_downstream_token("api://a", ["viewer"]))["sub"] == uid
        finally:
            current_identity.reset(tok)
    assert len(issuer.requests) == 2


def test_a_new_second_factor_gets_a_new_token(issuer):
    t0 = datetime.now(UTC) - timedelta(minutes=20)
    for mfa in (t0, datetime.now(UTC)):
        tok = current_identity.set(create_session("approver-1", "x@example.invalid", ["viewer", "approver"], mfa_auth_time=mfa))
        try:
            get_downstream_token("api://a", ["viewer", "approver"])
        finally:
            current_identity.reset(tok)
    assert len(issuer.requests) == 2


def test_without_roles_the_token_is_least_privilege_not_every_role(issuer):
    tok = current_identity.set(create_session("viewer-1", "x@example.invalid", ["viewer"]))
    try:
        assert claims(get_downstream_token("api://a"))["roles"] == ["viewer"]
    finally:
        current_identity.reset(tok)


def test_no_user_means_the_service_identity_with_only_the_roles_asked_for(issuer):
    c = claims(get_downstream_token("api://a", ["bff"]))
    assert c["sub"] == "svc-api-bff" and c["roles"] == ["bff"]


def test_the_headers_use_the_authenticated_user_not_a_caller_supplied_one(issuer):
    tok = current_identity.set(create_session("buyer-1", "x@example.invalid", ["viewer", "buyer"]))
    try:
        h = DownstreamClient("http://x", "api://a")._headers("someone-else", ["viewer", "buyer"])
    finally:
        current_identity.reset(tok)
    assert claims(h["Authorization"].removeprefix("Bearer "))["sub"] == "buyer-1"


def test_production_never_falls_back_to_a_fabricated_token(monkeypatch):
    base._token_cache.clear()
    monkeypatch.delenv("MMI_TEST_SERVICE_TOKEN", raising=False)
    monkeypatch.delenv("MMI_DEV_ISSUER_URL", raising=False)
    with pytest.raises(RuntimeError):
        get_downstream_token("api://a", ["viewer"])
    assert os.environ.get("MMI_DEV_ISSUER_URL") is None
