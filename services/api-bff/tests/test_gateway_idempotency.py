"""T047 (ADR-023): which gateway mutations carry an idempotency key, and that a repeated key reaches the owner unchanged.

The gateway does not deduplicate; the owning domain does. What the gateway must guarantee is that the key is
required where it is declared and is forwarded byte for byte on every attempt. All other mutating routes rely on the
domain's own state rules (see docs/architecture/integration/gateway-review.md); adding a new keyed route, or
removing the key from this one, must be a conscious decision recorded in this test.
"""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from routes.api import get_procurement_client
from tests_support import headers_for

KEYED = {
    ("/api/scenarios", "POST"),
    # MMI-6 (spec 007, FR-014): a retry of a lost-response terms save must not look like a stale revision. The procurement service stores the key
    # with the request hash and the version it created; the gateway only forwards it (tests/test_terms_idempotency_forwarding.py).
    ("/api/suppliers/{supplier_id}/terms", "PUT"),
    ("/api/product-suppliers/{variant_id}/{supplier_id}/terms", "PUT"),
}
KEY = "abcdefgh-retry-1"


def keyed_routes() -> set[tuple[str, str]]:
    from main import app

    return {(path, method.upper()) for path, ops in app.openapi()["paths"].items() for method, op in ops.items()
            if any(p.get("in") == "header" and p["name"].lower() == "idempotency-key" for p in op.get("parameters", []))}


def test_only_the_recorded_routes_declare_an_idempotency_key():
    assert keyed_routes() == KEYED


def test_a_repeated_key_is_forwarded_unchanged_every_time(role_store):
    from main import app

    proc = AsyncMock()
    proc.forward.return_value = {"id": "s1"}
    app.dependency_overrides[get_procurement_client] = lambda: proc
    try:
        client = TestClient(app)
        headers = {**headers_for("buyer-1", ["viewer", "buyer"]), "Idempotency-Key": KEY}
        first = client.post("/api/scenarios", headers=headers, json={"name": "x"})
        second = client.post("/api/scenarios", headers=headers, json={"name": "x"})
    finally:
        app.dependency_overrides.clear()
    assert first.status_code == second.status_code == 201
    assert [c.kwargs["extra_headers"] for c in proc.forward.call_args_list] == [{"Idempotency-Key": KEY}] * 2
