"""T145: scenario routes - roles, idempotency key forwarded, downloads pass through."""

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from routes.api import get_procurement_client
from tests_support import headers_for

BUYER = ["viewer", "buyer"]


def call(method, path, headers, proc, **kw):
    from main import app

    app.dependency_overrides[get_procurement_client] = lambda: proc
    try:
        return TestClient(app).request(method, path, headers=headers, **kw)
    finally:
        app.dependency_overrides.clear()


def test_only_buyers_create_and_promote_and_the_idempotency_key_is_required_and_forwarded(role_store):
    proc = AsyncMock()
    proc.forward.return_value = {"id": "s1"}
    assert call("POST", "/api/scenarios", {**headers_for("v", ["viewer"]), "Idempotency-Key": "abcdefgh1"}, proc, json={"name": "x"}).status_code == 403
    assert call("POST", "/api/scenarios/s1/promote", headers_for("a", ["viewer", "approver"]), proc, json={}).status_code == 403
    proc.forward.assert_not_called()
    missing = call("POST", "/api/scenarios", headers_for("b", BUYER), proc, json={"name": "x"})
    assert missing.status_code == 422 and missing.json() == {"detail": "idempotency_key_required"}
    ok = call("POST", "/api/scenarios", {**headers_for("buyer-1", BUYER), "Idempotency-Key": "abcdefgh1"}, proc, json={"name": "x"})
    assert ok.status_code == 201
    kw = proc.forward.call_args.kwargs
    assert kw["extra_headers"] == {"Idempotency-Key": "abcdefgh1"} and kw["user_id"] == "buyer-1" and kw["json"] == {"name": "x"}


def test_reading_listing_and_promoting_are_forwarded_for_the_signed_in_user(role_store):
    proc = AsyncMock()
    proc.forward.return_value = {"scenarios": []}
    assert call("GET", "/api/scenarios", headers_for("v", ["viewer"]), proc).json() == {"scenarios": []}
    assert call("GET", "/api/scenarios/s1", headers_for("v", ["viewer"]), proc).status_code == 200
    assert call("GET", "/api/scenarios", {}, proc).status_code == 401
    call("POST", "/api/scenarios/s1/promote", headers_for("buyer-1", BUYER), proc, json={"week": "2026-W46"})
    assert proc.forward.call_args.args == ("POST", "/scenarios/s1/promote") and proc.forward.call_args.kwargs["json"] == {"week": "2026-W46"}


def test_the_export_passes_the_file_through_and_validates_the_format(role_store):
    proc = AsyncMock()
    res = MagicMock()
    res.content, res.headers = b"a;b\r\n", {"content-type": "text/csv; charset=utf-8", "content-disposition": 'attachment; filename="escenario.csv"'}
    proc.forward_raw.return_value = res
    ok = call("GET", "/api/scenarios/s1/export?format=csv", headers_for("v", ["viewer"]), proc)
    assert ok.content == b"a;b\r\n" and "escenario.csv" in ok.headers["content-disposition"]
    assert call("GET", "/api/scenarios/s1/export?format=pdf", headers_for("v", ["viewer"]), proc).status_code == 422
