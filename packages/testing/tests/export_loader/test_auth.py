"""T089: audience-scoped service identities for the loader (constitution Principle IV, FR-039)."""

from datetime import UTC, datetime, timedelta

import pytest
from export_loader import auth
from mmi_common.auth import AuthError, DevIssuer, TokenValidator

ISSUER = "http://dev-issuer.local"


@pytest.fixture
def issuer():
    return DevIssuer(ISSUER)


@pytest.fixture
def gate(issuer):
    return auth.LoaderAuth(TokenValidator(ISSUER, auth.AUDIENCE, issuer.public_key))


def bearer(token: str) -> str:
    return f"Bearer {token}"


def test_bff_token_with_the_right_audience_is_accepted(issuer, gate):
    p = gate.check(bearer(issuer.issue("svc-api-bff", auth.AUDIENCE, ["bff"])))
    assert p.subject == "svc-api-bff"


def test_cli_token_is_accepted(issuer, gate):
    assert gate.check(bearer(issuer.issue("svc-local-loader-cli", auth.AUDIENCE, ["local-loader"]))).subject == "svc-local-loader-cli"


def test_missing_header_is_401(gate):
    with pytest.raises(AuthError) as exc:
        gate.check(None)
    assert exc.value.status == 401


def test_wrong_audience_is_401(issuer, gate):
    with pytest.raises(AuthError) as exc:
        gate.check(bearer(issuer.issue("svc-api-bff", "api://mmi-procurement-service", ["bff"])))
    assert exc.value.status == 401


def test_expired_token_is_401(issuer, gate):
    old = datetime.now(UTC) - timedelta(hours=2)
    with pytest.raises(AuthError) as exc:
        gate.check(bearer(issuer.issue("svc-api-bff", auth.AUDIENCE, ["bff"], now=old)))
    assert exc.value.status == 401


def test_token_signed_by_another_issuer_is_401(gate):
    other = DevIssuer(ISSUER)
    with pytest.raises(AuthError) as exc:
        gate.check(bearer(other.issue("svc-api-bff", auth.AUDIENCE, ["bff"])))
    assert exc.value.status == 401


@pytest.mark.parametrize("subject", ["svc-other", "buyer-1", "dev-anything"])
def test_other_subjects_are_403(issuer, gate, subject):
    with pytest.raises(AuthError) as exc:
        gate.check(bearer(issuer.issue(subject, auth.AUDIENCE, ["bff"])))
    assert exc.value.status == 403


def test_validator_from_env_refuses_outside_dev(monkeypatch):
    monkeypatch.setenv("MMI_ENV", "prod")
    with pytest.raises(RuntimeError):
        auth.validator_from_env()


def test_loader_principal_token_uses_the_loader_subject(monkeypatch):
    calls = {}

    def fake(audience, subject, roles=None, ttl_s=240.0):
        calls.update(audience=audience, subject=subject, roles=roles)
        return "tok"

    monkeypatch.setattr(auth, "service_token", fake)
    assert auth.loader_token("api://mmi-procurement-service") == "tok"
    assert calls == {"audience": "api://mmi-procurement-service", "subject": "svc-local-loader", "roles": ["local-loader"]}
