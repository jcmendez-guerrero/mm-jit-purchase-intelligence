"""T029: the dev-login endpoint mints sessions with caller-chosen roles, so it must be off unless explicitly enabled and never in prod."""

import pytest
from auth import session as session_module
from fastapi.testclient import TestClient


def client():
    from main import app

    return TestClient(app)


def login(**body):
    return client().post("/api/auth/dev-login", json={"user_id": "buyer-1", "email": "x@example.invalid", "roles": ["viewer", "admin"], **body})


def test_dev_login_is_off_by_default(monkeypatch):
    monkeypatch.setenv("MMI_ENV", "dev")
    assert login().status_code == 404


def test_the_flag_alone_does_not_enable_it_in_production(monkeypatch):
    monkeypatch.setenv("MMI_ENV", "prod")
    monkeypatch.setenv("MMI_ENABLE_DEV_LOGIN", "1")
    assert login().status_code == 404


def test_the_flag_enables_it_in_development(monkeypatch):
    monkeypatch.setenv("MMI_ENV", "dev")
    monkeypatch.setenv("MMI_ENABLE_DEV_LOGIN", "1")
    assert login().status_code == 200


def test_a_known_user_gets_the_registry_roles_not_the_requested_ones(monkeypatch):
    monkeypatch.setenv("MMI_ENV", "dev")
    monkeypatch.setenv("MMI_ENABLE_DEV_LOGIN", "1")
    res = login()                                                    # buyer-1 asks for admin
    assert res.json()["roles"] == ["buyer", "viewer"]


def test_an_unknown_user_can_only_be_a_viewer(monkeypatch):
    monkeypatch.setenv("MMI_ENV", "dev")
    monkeypatch.setenv("MMI_ENABLE_DEV_LOGIN", "1")
    assert login(user_id="stranger-1").json()["roles"] == ["viewer"]


def test_production_refuses_to_sign_sessions_without_a_real_secret(monkeypatch):
    monkeypatch.setenv("MMI_ENV", "prod")
    monkeypatch.delenv("MMI_SESSION_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        session_module.get_secret_key()
    monkeypatch.setenv("MMI_SESSION_SECRET", "short")
    with pytest.raises(RuntimeError):
        session_module.get_secret_key()
    monkeypatch.setenv("MMI_SESSION_SECRET", "x" * 40)
    assert session_module.get_secret_key() == b"x" * 40


def test_development_keeps_working_without_a_secret(monkeypatch):
    monkeypatch.setenv("MMI_ENV", "dev")
    monkeypatch.delenv("MMI_SESSION_SECRET", raising=False)
    assert session_module.get_secret_key()
