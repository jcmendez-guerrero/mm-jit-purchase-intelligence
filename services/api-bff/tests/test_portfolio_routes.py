"""T063: BFF portfolio routes - any signed-in role reads, only the filters that were set are forwarded, bad paging is refused first."""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from routes.api import get_inventory_client
from tests_support import headers_for

BODY = {"active_products": 7, "by_class": [], "by_eligibility": [], "by_confidence": [], "worst_quality": []}


def call(path, headers, inv):
    from main import app

    app.dependency_overrides[get_inventory_client] = lambda: inv
    try:
        return TestClient(app).get(path, headers=headers)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("roles", [["viewer"], ["viewer", "buyer"], ["viewer", "approver"], ["viewer", "admin"]])
def test_every_signed_in_role_can_read_the_portfolio(role_store, roles):
    inv = AsyncMock()
    inv.forward.return_value = BODY
    r = call("/api/quality/portfolio", headers_for("u", roles), inv)
    assert r.status_code == 200 and r.json() == BODY
    assert inv.forward.call_args.args[:2] == ("GET", "/quality/portfolio") and inv.forward.call_args.kwargs["params"] is None


def test_only_the_filters_that_were_set_are_forwarded(role_store):
    inv = AsyncMock()
    inv.forward.return_value = BODY
    call("/api/quality/portfolio?category=A&supplier_id=s1", headers_for("u", ["viewer"]), inv)
    assert inv.forward.call_args.kwargs["params"] == {"category": "A", "supplier_id": "s1"}


def test_a_drill_down_forwards_the_bucket_the_filters_and_the_paging(role_store):
    inv = AsyncMock()
    inv.forward.return_value = {"bucket": "eligibility", "key": "pending", "total": 3, "skus": ["EJ-1"]}
    r = call("/api/quality/portfolio/products?bucket=eligibility&key=pending&category=B&limit=20&offset=40", headers_for("u", ["viewer"]), inv)
    assert r.status_code == 200
    assert inv.forward.call_args.args[:2] == ("GET", "/quality/portfolio/products")
    assert inv.forward.call_args.kwargs["params"] == {"bucket": "eligibility", "key": "pending", "category": "B", "limit": 20, "offset": 40}


@pytest.mark.parametrize("query", ["bucket=class&key=AX&limit=0", "bucket=class&key=AX&limit=201", "bucket=class&key=AX&offset=-1", f"bucket=class&key={'x' * 41}", "key=AX"])
def test_bad_paging_or_missing_or_overlong_input_is_refused_before_anything_downstream(role_store, query):
    inv = AsyncMock()
    assert call(f"/api/quality/portfolio/products?{query}", headers_for("u", ["viewer"]), inv).status_code == 422
    inv.forward.assert_not_called()


def test_an_unauthenticated_call_is_refused(role_store):
    inv = AsyncMock()
    assert call("/api/quality/portfolio", {}, inv).status_code == 401
    inv.forward.assert_not_called()


def test_a_downstream_refusal_keeps_its_code(role_store):
    inv = AsyncMock()
    req = httpx.Request("GET", "http://x")
    inv.forward.side_effect = httpx.HTTPStatusError("x", request=req, response=httpx.Response(422, request=req, json={"detail": "request_invalid"}))
    r = call("/api/quality/portfolio?category=Z", headers_for("u", ["viewer"]), inv)
    assert r.status_code == 422 and r.json() == {"detail": "request_invalid"}


def test_the_origin_is_forwarded_for_the_counts_and_the_drill_down(role_store):
    inv = AsyncMock()
    inv.forward.return_value = BODY
    call("/api/quality/portfolio?origin=local_export", headers_for("u", ["viewer"]), inv)
    assert inv.forward.call_args.kwargs["params"] == {"origin": "local_export"}
    call("/api/quality/portfolio/products?bucket=class&key=AX&origin=erp", headers_for("u", ["viewer"]), inv)
    assert inv.forward.call_args.kwargs["params"]["origin"] == "erp"


@pytest.mark.parametrize("path", ["/api/quality/portfolio?origin=seed", "/api/quality/portfolio/products?bucket=class&key=AX&origin=x"])
def test_an_unknown_origin_is_refused_before_anything_downstream(role_store, path):
    inv = AsyncMock()
    assert call(path, headers_for("u", ["viewer"]), inv).status_code == 422
    inv.forward.assert_not_called()
