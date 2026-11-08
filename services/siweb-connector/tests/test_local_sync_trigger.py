"""T103: the local-only sync trigger: mounted only for the local loader, role-gated, mock host only."""

import pytest
from fastapi.testclient import TestClient
from local_sync import LOCAL_HOSTS, register
from mmi_common.auth import DevIssuer, TokenValidator
from mmi_common.service import create_service_app

ISSUER = "http://dev-issuer.local"
AUD = "api://mmi-siweb-connector"
LOCAL_ENV = {"MMI_LOCAL_LOADER": "1", "MMI_ENV": "dev", "MMI_SIWEB_BASE_URL": "http://siweb-mock:8089"}


def make(env, runner=None):
    issuer = DevIssuer(ISSUER)
    app = create_service_app("siweb-connector", TokenValidator(ISSUER, AUD, issuer.public_key))
    calls: list[list[str]] = []

    def default_runner(kinds, **_kw):
        calls.append(list(kinds))
        return 0

    register(app, runner or default_runner, env)
    return TestClient(app), issuer, calls


def token(issuer, roles=("local-loader",)):
    return {"Authorization": f"Bearer {issuer.issue('svc-local-loader', AUD, list(roles))}"}


def test_route_is_not_mounted_without_the_flag():
    c, issuer, _ = make({"MMI_ENV": "dev", "MMI_SIWEB_BASE_URL": "http://siweb-mock:8089"})
    assert c.post("/internal/local-sync", headers=token(issuer)).status_code == 404


@pytest.mark.parametrize("env_name", ["prod", "staging"])
def test_route_is_not_mounted_in_cloud_environments_even_with_the_flag(env_name):
    c, issuer, _ = make({**LOCAL_ENV, "MMI_ENV": env_name})
    assert c.post("/internal/local-sync", headers=token(issuer)).status_code == 404


def test_it_needs_the_loader_identity():
    c, issuer, calls = make(LOCAL_ENV)
    assert c.post("/internal/local-sync").status_code == 401
    assert c.post("/internal/local-sync", headers=token(issuer, roles=("bff",))).status_code == 403
    assert calls == []


def test_it_runs_the_collection_in_process():
    c, issuer, calls = make(LOCAL_ENV)
    r = c.post("/internal/local-sync", headers=token(issuer))
    assert r.status_code == 200 and r.json() == {"ok": True, "exit_code": 0}
    assert len(calls) == 1 and {"warehouses", "products", "variants", "movements", "lots"} <= set(calls[0])


def test_a_failed_run_is_reported():
    c, issuer, _ = make(LOCAL_ENV, lambda kinds, **_kw: 1)
    assert c.post("/internal/local-sync", headers=token(issuer)).json() == {"ok": False, "exit_code": 1}


@pytest.mark.parametrize("base", ["https://api.example.com", "http://203.0.113.9", "https://host.example.test"])
def test_it_refuses_any_host_that_is_not_the_mock(base):
    c, issuer, calls = make({**LOCAL_ENV, "MMI_SIWEB_BASE_URL": base})
    r = c.post("/internal/local-sync", headers=token(issuer))
    assert r.status_code == 403 and calls == []


def test_local_hosts_are_only_local_names():
    assert LOCAL_HOSTS == {"siweb-mock", "localhost", "127.0.0.1", "::1"}
