"""T044/T052 (FR-012 to FR-019): supplier management through the BFF: buyers and admins write, everyone signed in reads, If-Match and stable codes pass through."""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from routes.api import get_procurement_client
from tests_support import headers_for

BUYER = headers_for("buyer-1", ["viewer", "buyer"])
ADMIN = headers_for("admin-1", ["viewer", "admin"])
APPROVER = headers_for("approver-1", ["viewer", "approver"])
VIEWER = headers_for("viewer-1", ["viewer"])
BODY = {"name": "Proveedor Sintetico", "fiscal_type": "national", "country": "ES", "currency": "EUR"}


def app_with(mock):
    from main import app

    app.dependency_overrides[get_procurement_client] = lambda: mock
    return app


def call(method, path, mock=None, **kw):
    mock = mock or AsyncMock()
    app = app_with(mock)
    try:
        return TestClient(app).request(method, f"/api{path}", **kw), mock
    finally:
        app.dependency_overrides.clear()


def refusal(status, body, method="POST"):
    req = httpx.Request(method, "http://procurement/x")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(status, request=req, json=body))


WRITES = [
    ("POST", "/suppliers", {"json": BODY}), ("PATCH", "/suppliers/s1", {"json": {"currency": "EUR"}, "headers": {}}),
    ("POST", "/suppliers/s1/deactivate", {"json": {"confirm": False}}), ("POST", "/suppliers/s1/reactivate", {}),
    ("POST", "/suppliers/s1/merge", {"json": {"merge_into": "s2"}}), ("PUT", "/suppliers/s1/links/SYN-1", {"json": {"cost": "1.00"}}),
    ("DELETE", "/suppliers/s1/links/SYN-1", {}), ("POST", "/suppliers/s1/links/bulk/preview", {"json": {"q": "pienso"}}),
    ("POST", "/suppliers/s1/links/bulk/apply", {"json": {"batch_id": "b1"}}), ("POST", "/suppliers/review-items/i1/resolve", {"json": {"decision": "ignore"}}),
]


@pytest.mark.parametrize(("method", "path", "kw"), WRITES, ids=[f"{m} {p}" for m, p, _ in WRITES])
def test_viewers_and_approvers_cannot_write(method, path, kw, role_store):
    for who in (VIEWER, APPROVER):
        res, mock = call(method, path, headers={**who, **kw.get("headers", {})}, **{k: v for k, v in kw.items() if k != "headers"})
        assert res.status_code == 403 and res.json() == {"detail": "auth_forbidden_role"}
        mock.forward.assert_not_called()


def test_buyers_and_admins_can_create_and_the_roles_travel_downstream(role_store):
    for who in (BUYER, ADMIN):
        mock = AsyncMock()
        mock.forward.return_value = {"id": "s1", **BODY}
        res, mock = call("POST", "/suppliers", mock, json=BODY, headers=who)
        assert res.status_code == 200 or res.status_code == 201
        method, path = mock.forward.call_args.args[:2]
        assert (method, path) == ("POST", "/suppliers") and mock.forward.call_args.kwargs["json"] == BODY and mock.forward.call_args.kwargs["roles"]


def test_anyone_signed_in_can_read_but_anonymous_cannot(role_store):
    mock = AsyncMock()
    mock.forward.return_value = {"id": "s1"}
    assert call("GET", "/suppliers/s1", mock, headers=VIEWER)[0].status_code == 200
    assert call("GET", "/suppliers/s1/links", mock, headers=VIEWER)[0].status_code == 200
    assert call("GET", "/suppliers/review-items", mock, headers=APPROVER)[0].status_code == 200
    assert call("GET", "/suppliers/s1")[0].status_code == 401


def test_list_filters_are_forwarded(role_store):
    mock = AsyncMock()
    mock.get_suppliers.return_value = []
    res, mock = call("GET", "/suppliers?status=active&classification=purchasing&q=alfa", mock, headers=VIEWER)
    assert res.status_code == 200 and mock.get_suppliers.call_args.kwargs["params"] == {"status": "active", "classification": "purchasing", "q": "alfa"}


def test_patch_forwards_if_match_and_requires_it(role_store):
    mock = AsyncMock()
    mock.forward.return_value = {"id": "s1", "version": 2}
    res, mock = call("PATCH", "/suppliers/s1", mock, json={"currency": "EUR"}, headers={**BUYER, "If-Match": '"1"'})
    assert res.status_code == 200 and mock.forward.call_args.kwargs["if_match"] == '"1"'
    res, mock = call("PATCH", "/suppliers/s1", AsyncMock(), json={"currency": "EUR"}, headers=BUYER)
    assert res.status_code == 428 and res.json() == {"detail": "revision_required"}


def test_downstream_refusals_keep_their_codes_and_useful_details(role_store):
    mock = AsyncMock()
    mock.forward.side_effect = refusal(409, {"detail": "supplier_possible_duplicate", "duplicates": ["s7"]})
    res, _ = call("POST", "/suppliers", mock, json=BODY, headers=BUYER)
    assert res.status_code == 409 and res.json() == {"detail": "supplier_possible_duplicate", "duplicates": ["s7"]}
    mock.forward.side_effect = refusal(412, {"detail": "supplier_version_conflict", "current_version": 4}, "PATCH")
    res, _ = call("PATCH", "/suppliers/s1", mock, json={"currency": "EUR"}, headers={**BUYER, "If-Match": '"1"'})
    assert res.status_code == 412 and res.json() == {"detail": "supplier_version_conflict", "current_version": 4}
    mock.forward.side_effect = refusal(422, {"detail": "supplier_invalid", "field": "country"})
    assert call("POST", "/suppliers", mock, json=BODY, headers=BUYER)[0].json() == {"detail": "supplier_invalid", "field": "country"}
    mock.forward.side_effect = refusal(409, {"detail": "merge_open_lines", "open_lines": 3})
    assert call("POST", "/suppliers/s1/merge", mock, json={"merge_into": "s2"}, headers=BUYER)[0].json() == {"detail": "merge_open_lines", "open_lines": 3}


def test_free_text_in_a_downstream_refusal_is_never_echoed(role_store):
    mock = AsyncMock()
    mock.forward.side_effect = refusal(422, {"detail": "Nombre: Proveedor Real S.L.", "field": "x y z", "duplicates": "no es una lista"})
    res, _ = call("POST", "/suppliers", mock, json=BODY, headers=BUYER)
    assert res.json() == {"detail": "downstream_refused"}


def test_sku_paths_are_encoded_and_checked(role_store):
    mock = AsyncMock()
    mock.forward.return_value = {}
    call("PUT", "/suppliers/s1/links/SYN%2F01%20A", mock, json={"cost": "1.00"}, headers=BUYER)
    assert mock.forward.call_args.args[1] == "/suppliers/s1/links/SYN%2F01%20A"
    res, mock2 = call("PUT", "/suppliers/s1/links/" + "x" * 61, AsyncMock(), json={"cost": "1.00"}, headers=BUYER)
    assert res.status_code == 422 and res.json() == {"detail": "request_invalid"}
    mock2.forward.assert_not_called()


def test_bulk_and_deactivation_bodies_pass_through(role_store):
    mock = AsyncMock()
    mock.forward.return_value = {"batch_id": "b1", "matched": 2}
    res, mock = call("POST", "/suppliers/s1/links/bulk/preview", mock, json={"skus": ["A", "B"]}, headers=BUYER)
    assert res.json()["matched"] == 2 and mock.forward.call_args.kwargs["json"] == {"skus": ["A", "B"]}
    res, mock = call("POST", "/suppliers/s1/deactivate", mock, json={"confirm": True}, headers=ADMIN)
    assert mock.forward.call_args.args[:2] == ("POST", "/suppliers/s1/deactivate")


def test_the_assignment_file_is_checked_and_forwarded(role_store):
    mock = AsyncMock()
    resp = httpx.Response(200, json={"groups": {}, "errors": [], "rows": 0})
    mock.forward_raw.return_value = resp
    res, mock = call("POST", "/links/bulk/file", mock, files={"file": ("a.csv", b"SKU;Proveedor\n", "text/csv")}, headers=BUYER)
    assert res.status_code == 200 and mock.forward_raw.call_args.args[:2] == ("POST", "/links/bulk/file")
    res, mock = call("POST", "/links/bulk/file", AsyncMock(), files={"file": ("a.xlsm", b"x", "text/csv")}, headers=BUYER)
    assert res.status_code == 415 and res.json() == {"detail": "import_type_not_allowed"}


def test_review_resolution_returns_no_content(role_store):
    mock = AsyncMock()
    mock.forward.return_value = {}
    res, _ = call("POST", "/suppliers/review-items/i-123/resolve", mock, json={"decision": "keep_both"}, headers=BUYER)
    assert res.status_code == 204
