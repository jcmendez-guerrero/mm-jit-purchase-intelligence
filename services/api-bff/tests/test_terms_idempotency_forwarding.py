"""T022 (FR-014): the BFF passes an Idempotency-Key on the two terms saves through to procurement unchanged, and adds nothing when there is none."""

from unittest.mock import AsyncMock

import httpx
import pytest
from clients.procurement import ProcurementClient
from fastapi.testclient import TestClient
from routes.api import get_procurement_client
from tests_support import headers_for

BUYER = ["viewer", "buyer"]


def app_with(mock):
    from main import app

    app.dependency_overrides[get_procurement_client] = lambda: mock
    return app


def test_both_saves_forward_the_key_and_a_save_without_one_forwards_none(role_store):
    mock = AsyncMock()
    mock.put_supplier_terms.return_value = {"version": 2}
    mock.put_override_terms.return_value = {"version": 1}
    app = app_with(mock)
    try:
        client = TestClient(app)
        keyed = {**headers_for("buyer-1", BUYER), "Idempotency-Key": "k-1"}
        assert client.put("/api/suppliers/s1/terms", json={"lead_time_days": 4}, headers=keyed).status_code == 200
        assert client.put("/api/product-suppliers/1/s1/terms", json={"lead_time_days": 4}, headers=keyed).status_code == 200
        assert client.put("/api/suppliers/s1/terms", json={"lead_time_days": 4}, headers=headers_for("buyer-1", BUYER)).status_code == 200
    finally:
        app.dependency_overrides.clear()
    assert mock.put_supplier_terms.call_args_list[0].kwargs["idempotency_key"] == "k-1"
    assert mock.put_supplier_terms.call_args_list[1].kwargs["idempotency_key"] is None
    assert mock.put_override_terms.call_args.kwargs["idempotency_key"] == "k-1"


def test_the_idempotency_refusals_from_procurement_reach_the_user(role_store):
    req = httpx.Request("PUT", "http://procurement/suppliers/s1/terms")
    mock = AsyncMock()
    mock.put_supplier_terms.side_effect = httpx.HTTPStatusError("x", request=req, response=httpx.Response(422, request=req, json={"detail": "idempotency_key_reuse"}))
    app = app_with(mock)
    try:
        res = TestClient(app).put("/api/suppliers/s1/terms", json={}, headers={**headers_for("buyer-1", BUYER), "Idempotency-Key": "k-1"})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 422 and res.json() == {"detail": "idempotency_key_reuse"}


@pytest.mark.asyncio
async def test_the_client_sends_the_key_next_to_if_match_as_a_header():
    client = ProcurementClient("http://procurement")
    client.put = AsyncMock(return_value=httpx.Response(200, json={"version": 3}, request=httpx.Request("PUT", "http://procurement/x")))
    assert await client.put_supplier_terms("s1", {}, "buyer-1", ["buyer"], if_match='"2"', idempotency_key="k-9") == {"version": 3}
    assert client.put.call_args.kwargs["extra_headers"] == {"If-Match": '"2"', "Idempotency-Key": "k-9"}
    await client.put_override_terms(1, "s1", {}, "buyer-1", ["buyer"], idempotency_key="k-10")
    assert client.put.call_args.kwargs["extra_headers"] == {"Idempotency-Key": "k-10"}
    await client.put_supplier_terms("s1", {}, "buyer-1", ["buyer"])
    assert client.put.call_args.kwargs["extra_headers"] is None
