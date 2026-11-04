import pytest
from fastapi.testclient import TestClient
from mmi_common.auth import DevIssuer, TokenValidator
from mmi_common.service import create_service_app, validator_from_env


@pytest.fixture
def setup():
    issuer = DevIssuer()
    app = create_service_app("demo", validator=TokenValidator(issuer.issuer, "api://mmi-demo", issuer.public_key))
    return issuer, TestClient(app)


def test_health_endpoints_need_no_auth(setup):
    _, c = setup
    assert c.get("/healthz").json() == {"status": "ok", "service": "demo"}
    assert c.get("/readyz").status_code == 200


def test_whoami_requires_valid_token(setup):
    issuer, c = setup
    assert c.get("/whoami").status_code == 401
    assert c.get("/whoami", headers={"Authorization": "Bearer junk"}).status_code == 401
    wrong_aud = issuer.issue("u", "api://other")
    assert c.get("/whoami", headers={"Authorization": f"Bearer {wrong_aud}"}).status_code == 401
    ok = issuer.issue("svc", "api://mmi-demo", roles=["reader"])
    r = c.get("/whoami", headers={"Authorization": f"Bearer {ok}"})
    assert r.status_code == 200 and r.json() == {"subject": "svc", "roles": ["reader"]}


def test_readiness_failure_is_503():
    app = create_service_app("demo", validator=None, readiness=[lambda: False])
    assert TestClient(app).get("/readyz").status_code == 503


def test_dev_issuer_refused_outside_dev(monkeypatch):
    monkeypatch.setenv("MMI_DEV_ISSUER_URL", "http://x")
    monkeypatch.setenv("MMI_ENV", "production")
    with pytest.raises(RuntimeError):
        validator_from_env("api://a")
