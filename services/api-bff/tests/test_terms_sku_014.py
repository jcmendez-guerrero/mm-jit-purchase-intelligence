"""MMI-16 (spec 014): the product-supplier terms are read and saved at /api/product-suppliers/{sku}/{supplier_id}/terms; the variant-id path is gone."""

from unittest.mock import AsyncMock

import httpx
import pytest
from clients.procurement import ProcurementClient
from fastapi.testclient import TestClient
from routes.api import get_procurement_client
from tests_support import headers_for

BUYER = ["viewer", "buyer"]
URL = "/api/product-suppliers/SYN-0001/s1/terms"


def app_with(mock):
    from main import app

    app.dependency_overrides[get_procurement_client] = lambda: mock
    return app


def refusal(status, code):
    req = httpx.Request("GET", "http://procurement/x")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(status, request=req, json={"detail": code}))


def test_every_signed_in_role_can_read_by_sku_and_the_call_carries_identity_and_roles(role_store):
    mock = AsyncMock()
    mock.get_override_terms.return_value = {"sku": "SYN-0001", "supplier_id": "s1", "version": 0, "override": None, "history": [], "effective": {}}
    app = app_with(mock)
    try:
        for roles in (["viewer"], BUYER, ["viewer", "approver"], ["viewer", "admin"]):
            res = TestClient(app).get(URL + "?as_of=2026-01-01T00:00:00Z", headers=headers_for("reader-1", roles))
            assert res.status_code == 200 and "variant_id" not in res.text
            assert mock.get_override_terms.call_args.args[:2] == ("SYN-0001", "s1")
            assert mock.get_override_terms.call_args.kwargs == {"as_of": "2026-01-01T00:00:00Z", "roles": roles}
        assert TestClient(app).get(URL).status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("code", ["sku_unknown", "sku_ambiguous"])
def test_the_refusals_for_a_bad_sku_reach_the_user_unchanged(role_store, code):
    mock = AsyncMock()
    mock.get_override_terms.side_effect = refusal(422, code)
    mock.put_override_terms.side_effect = refusal(422, code)
    app = app_with(mock)
    try:
        h = headers_for("buyer-1", BUYER)
        for res in (TestClient(app).get(URL, headers=h), TestClient(app).put(URL, json={"lead_time_days": 3}, headers=h)):
            assert res.status_code == 422 and res.json() == {"detail": code}
    finally:
        app.dependency_overrides.clear()


def test_a_nul_byte_in_the_sku_is_refused_before_the_service_is_called(role_store):
    mock = AsyncMock()
    app = app_with(mock)
    try:
        res = TestClient(app).get("/api/product-suppliers/SYN%00/s1/terms", headers=headers_for("buyer-1", BUYER))
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 422 and res.json() == {"detail": "invalid_input"}
    mock.get_override_terms.assert_not_called()


def test_only_a_buyer_saves_and_the_precondition_and_the_key_are_forwarded(role_store):
    mock = AsyncMock()
    mock.put_override_terms.return_value = {"version": 1}
    app = app_with(mock)
    try:
        assert TestClient(app).put(URL, json={"pack_multiple": 6}, headers=headers_for("viewer-1", ["viewer"])).status_code == 403
        assert TestClient(app).put(URL, json={"pack_multiple": 6}, headers=headers_for("admin-1", ["viewer", "admin"])).status_code == 403
        mock.put_override_terms.assert_not_called()
        res = TestClient(app).put(URL, json={"pack_multiple": 6}, headers={**headers_for("buyer-1", BUYER), "If-Match": '"0"', "Idempotency-Key": "k-1"})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200 and res.json() == {"version": 1}
    kw = mock.put_override_terms.call_args.kwargs
    assert (kw["sku"], kw["supplier_id"], kw["body"], kw["if_match"], kw["idempotency_key"]) == ("SYN-0001", "s1", {"pack_multiple": 6}, '"0"', "k-1")
    assert "variant_id" not in kw


def test_a_sku_with_a_slash_and_accents_reaches_the_service_whole(role_store):
    mock = AsyncMock()
    mock.get_override_terms.return_value = {"sku": "SYN/áño-1"}
    mock.put_override_terms.return_value = {"version": 1}
    app = app_with(mock)
    path = "/api/product-suppliers/SYN%2F%C3%A1%C3%B1o-1/s1/terms"
    try:
        h = headers_for("buyer-1", BUYER)
        assert TestClient(app).get(path, headers=h).status_code == 200
        assert TestClient(app).put(path, json={"pack_multiple": 6}, headers=h).status_code == 200
    finally:
        app.dependency_overrides.clear()
    assert mock.get_override_terms.call_args.args[:2] == ("SYN/áño-1", "s1")
    assert mock.put_override_terms.call_args.kwargs["sku"] == "SYN/áño-1"


def test_the_variant_id_path_no_longer_means_a_variant(role_store):
    """A number in the path is just a SKU now: it is passed on as text and the service refuses it as unknown."""
    mock = AsyncMock()
    mock.get_override_terms.side_effect = refusal(422, "sku_unknown")
    app = app_with(mock)
    try:
        res = TestClient(app).get("/api/product-suppliers/9001/s1/terms", headers=headers_for("buyer-1", BUYER))
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 422 and mock.get_override_terms.call_args.args[0] == "9001"


@pytest.mark.asyncio
async def test_the_client_encodes_the_sku_and_the_supplier_in_the_path():
    client = ProcurementClient("http://procurement")
    ok = httpx.Response(200, json={}, request=httpx.Request("GET", "http://procurement/x"))
    client.get = AsyncMock(return_value=ok)
    client.put = AsyncMock(return_value=ok)
    await client.get_override_terms("SYN 0/1", "s/1", as_of=None, roles=["viewer"])
    assert client.get.call_args.args[0] == "/product-suppliers/SYN%200%2F1/s%2F1/terms"
    await client.put_override_terms(sku="SYN 0/1", supplier_id="s/1", body={}, user_id="buyer-1", roles=["buyer"])
    assert client.put.call_args.args[0] == "/product-suppliers/SYN%200%2F1/s%2F1/terms"
