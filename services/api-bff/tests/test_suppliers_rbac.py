"""T046: supplier terms routes - only buyers edit, refusals are audited, If-Match is forwarded, a stale save keeps its 412 and current version."""

from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient
from routes.api import get_procurement_client
from tests_support import headers_for

BUYER = ["viewer", "buyer"]


def app_with(mock):
    from main import app

    app.dependency_overrides[get_procurement_client] = lambda: mock
    return app


def http_error(status, body):
    req = httpx.Request("PUT", "http://procurement/suppliers/s1/terms")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(status, request=req, json=body))


def test_a_viewer_cannot_edit_terms_and_the_refusal_is_audited(role_store):
    mock = AsyncMock()
    app = app_with(mock)
    try:
        res = TestClient(app).put("/api/suppliers/s1/terms", json={"lead_time_days": 3}, headers=headers_for("viewer-1", ["viewer"]))
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 403 and res.json() == {"detail": "auth_forbidden_role"}
    mock.put_supplier_terms.assert_not_called()
    refusals = [e for e in role_store.audit_view() if e["action"] == "access.refused" and e["actor"] == "viewer-1"]
    assert refusals and "/api/suppliers/s1/terms" in refusals[-1]["target_user"]


def test_an_admin_without_the_buyer_role_cannot_edit_terms_either(role_store):
    app = app_with(AsyncMock())
    try:
        res = TestClient(app).put("/api/suppliers/s1/terms", json={}, headers=headers_for("admin-1", ["viewer", "admin"]))
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 403


def test_a_buyer_save_forwards_the_body_the_user_and_the_precondition(role_store):
    mock = AsyncMock()
    mock.put_supplier_terms.return_value = {"version": 2}
    app = app_with(mock)
    try:
        res = TestClient(app).put("/api/suppliers/s1/terms", json={"lead_time_days": 4}, headers={**headers_for("buyer-1", BUYER), "If-Match": '"1"'})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200 and res.json() == {"version": 2}
    kwargs = mock.put_supplier_terms.call_args.kwargs
    assert kwargs["supplier_id"] == "s1" and kwargs["terms"] == {"lead_time_days": 4} and kwargs["user_id"] == "buyer-1" and kwargs["if_match"] == '"1"'


def test_a_stale_save_keeps_its_412_and_names_the_current_version(role_store):
    mock = AsyncMock()
    mock.put_supplier_terms.side_effect = http_error(412, {"detail": "revision_conflict", "current_version": 5})
    app = app_with(mock)
    try:
        res = TestClient(app).put("/api/suppliers/s1/terms", json={}, headers={**headers_for("buyer-1", BUYER), "If-Match": '"2"'})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 412 and res.json() == {"detail": "revision_conflict", "current_version": 5}


def test_validation_codes_from_procurement_reach_the_user(role_store):
    mock = AsyncMock()
    mock.put_supplier_terms.side_effect = http_error(422, {"detail": "terms_threshold_below_minimum"})
    app = app_with(mock)
    try:
        res = TestClient(app).put("/api/suppliers/s1/terms", json={}, headers=headers_for("buyer-1", BUYER))
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 422 and res.json() == {"detail": "terms_threshold_below_minimum"}


def test_every_signed_in_role_can_read_terms_and_history(role_store):
    mock = AsyncMock()
    mock.get_supplier_terms.return_value = {"version": 2, "current": {"lead_time_days": 3}, "history": []}
    mock.get_override_terms.return_value = {"version": 0, "override": None, "effective": {}}
    app = app_with(mock)
    try:
        for roles in (["viewer"], BUYER, ["viewer", "approver"], ["viewer", "admin"]):
            h = headers_for("reader-1", roles)
            assert TestClient(app).get("/api/suppliers/s1/terms", headers=h).status_code == 200
            assert TestClient(app).get("/api/product-suppliers/9001/s1/terms", headers=h).status_code == 200
        assert TestClient(app).get("/api/suppliers/s1/terms").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_override_edits_need_the_buyer_role_and_forward_the_precondition(role_store):
    mock = AsyncMock()
    mock.put_override_terms.return_value = {"version": 1}
    app = app_with(mock)
    try:
        assert TestClient(app).put("/api/product-suppliers/9001/s1/terms", json={"pack_multiple": 6}, headers=headers_for("viewer-1", ["viewer"])).status_code == 403
        res = TestClient(app).put("/api/product-suppliers/9001/s1/terms", json={"pack_multiple": 6}, headers={**headers_for("buyer-1", BUYER), "If-Match": '"0"'})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    kw = mock.put_override_terms.call_args.kwargs
    assert (kw["variant_id"], kw["supplier_id"], kw["body"], kw["if_match"]) == (9001, "s1", {"pack_multiple": 6}, '"0"')
