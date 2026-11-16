"""Feature 011 (T085): the gateway is built with ``create_service_app``, so a NUL byte is refused before any route, session check or audit write runs.

The audit of a refusal stores the request path, so a NUL that got past this point would make PostgreSQL fail on the audit write itself.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from main import app

    return TestClient(app)


@pytest.mark.parametrize("path", ["/api/products/%00/effective-policy", "/api/products/SYN%00/criticality", "/api/policy-audit?scope=%00", "/api/%00"])
def test_a_nul_byte_in_the_path_or_query_is_refused_at_the_gateway(client, path):
    res = client.get(path)
    assert res.status_code == 422 and res.json() == {"detail": "invalid_input"}


@pytest.mark.parametrize("raw", [b'{"min_units": "a\\u0000b"}', b'{"min_units": "a\x00b"}'])
def test_a_nul_byte_in_a_json_body_is_refused_at_the_gateway(client, raw):
    res = client.put("/api/policies/global/*", content=raw, headers={"Content-Type": "application/json"})
    assert res.status_code == 422 and res.json() == {"detail": "invalid_input"}


def test_the_refusal_is_not_audited_as_an_access_refusal(client, role_store):
    """It is refused before the role checks, so it adds nothing to the refusal audit (no path with a NUL is ever stored)."""
    before = len(role_store.audit_view())
    client.get("/api/products/%00/effective-policy")
    assert len(role_store.audit_view()) == before
