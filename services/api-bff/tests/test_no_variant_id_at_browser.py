"""Feature 014 (T087, FR-008a): the browser never sees, sends or addresses a product by its internal `variant_id`; people and the browser use the SKU.

Service-to-service routes, events and the cost writer keep `variant_id` (machine-to-machine), so this file only looks at what the gateway exposes. Synthetic values only.
"""

import json

from fastapi.testclient import TestClient
from tests_support import headers_for


def openapi() -> dict:
    from main import app

    return app.openapi()


def test_no_gateway_path_parameter_query_parameter_or_schema_is_named_after_the_internal_id():
    spec = openapi()
    text = json.dumps(spec)
    for needle in ("variant_id", "variantId", "{variant"):
        assert needle not in text, f"the gateway contract still exposes {needle}"


def test_the_sku_keyed_routes_exist_and_the_id_keyed_ones_are_gone():
    paths = set(openapi()["paths"])
    for path in ("/api/dashboard/skus/{sku}/forecast-basis", "/api/inventory/skus/{sku}", "/api/product-suppliers/{sku}/{supplier_id}/terms"):
        assert path in paths, path
    for gone in ("/api/dashboard/variants/{variant_id}/forecast-basis", "/api/inventory/variants/{variant_id}", "/api/product-suppliers/{variant_id}/{supplier_id}/terms"):
        assert gone not in paths, gone


def test_every_json_response_is_scrubbed_of_variant_id_at_any_depth(role_store):
    from main import app
    from scrub import without_variant_ids

    payload = {"variant_id": 7, "rows": [{"variant_id": 8, "sku": "SYN-001", "nested": {"variant_id": 9, "keep": 1}}], "sku": "SYN-001"}
    assert without_variant_ids(payload) == {"rows": [{"sku": "SYN-001", "nested": {"keep": 1}}], "sku": "SYN-001"}
    assert without_variant_ids([{"variant_id": 1, "a": 2}, 3, "variant_id"]) == [{"a": 2}, 3, "variant_id"]

    @app.get("/api/_probe_variant_scrub")
    def probe() -> dict:
        return payload

    res = TestClient(app).get("/api/_probe_variant_scrub", headers=headers_for("buyer-1", ["buyer"]))
    assert res.status_code == 200
    assert "variant_id" not in res.text and res.json()["rows"][0]["sku"] == "SYN-001"


def _refusal(status: int, code: str):
    import httpx

    request = httpx.Request("GET", "http://x")
    return httpx.HTTPStatusError("refused", request=request, response=httpx.Response(status, json={"detail": code}, request=request))


def test_an_unknown_or_ambiguous_sku_keeps_its_stable_code_and_status(role_store):
    from unittest.mock import AsyncMock

    from main import app
    from routes.api import get_inventory_client, get_procurement_client

    for status, code in ((404, "sku_not_found"), (409, "sku_ambiguous")):
        inventory, procurement = AsyncMock(), AsyncMock()
        async def refuse(*_a, _status=status, _code=code, **_k):
            raise _refusal(_status, _code)

        inventory.internal_id.side_effect = refuse
        inventory.get_sku_detail.side_effect = refuse
        app.dependency_overrides[get_inventory_client] = lambda inventory=inventory: inventory
        app.dependency_overrides[get_procurement_client] = lambda procurement=procurement: procurement
        try:
            client, headers = TestClient(app), headers_for("buyer-1", ["viewer", "buyer"])
            for res in (client.get("/api/inventory/skus/SYN-001", headers=headers),
                        client.get("/api/lot-costs?sku=SYN-001&supplier_id=s1", headers=headers)):
                assert res.status_code == status and res.json() == {"detail": code}, (res.request.url, res.text)
            procurement.get_lot_costs.assert_not_called()                 # nothing reaches the services for a SKU that does not resolve
        finally:
            app.dependency_overrides.clear()


def test_two_cookies_on_a_json_answer_both_survive_the_scrub():
    from fastapi import Response
    from main import app

    @app.get("/api/_two_cookies")
    def two_cookies() -> Response:
        r = Response('{"a":1,"variant_id":2}', media_type="application/json")
        r.set_cookie("one", "1")
        r.set_cookie("two", "2")
        return r

    res = TestClient(app).get("/api/_two_cookies")
    assert res.json() == {"a": 1}
    assert len(res.headers.get_list("set-cookie")) == 2


def test_a_malformed_sku_is_refused_on_every_sku_route_before_any_service_is_called(role_store):
    from unittest.mock import AsyncMock

    from main import app
    from routes.api import get_inventory_client, get_procurement_client
    from routes.policies import get_forecast_client

    inventory, procurement, forecast = AsyncMock(), AsyncMock(), AsyncMock()
    app.dependency_overrides[get_inventory_client] = lambda: inventory
    app.dependency_overrides[get_procurement_client] = lambda: procurement
    app.dependency_overrides[get_forecast_client] = lambda: forecast
    try:
        client, headers = TestClient(app), headers_for("buyer-1", ["viewer", "buyer"])
        for bad in (".hidden", "-x", "a%20b", "%2e%2e"):
            for res in (client.get(f"/api/inventory/skus/{bad}", headers=headers), client.get(f"/api/dashboard/skus/{bad}/forecast-basis", headers=headers),
                        client.get(f"/api/lot-costs?sku={bad}&supplier_id=s1", headers=headers),
                        client.post("/api/lot-costs", json={"sku": bad.replace("%20", " ")}, headers=headers),
                        client.post("/api/cost-updates", json={"sku": bad.replace("%20", " "), "supplier_id": "s1"}, headers=headers)):
                assert res.status_code == 422, (bad, res.request.url, res.status_code)
        inventory.internal_id.assert_not_called()
        inventory.internal_ids.assert_not_called()
        inventory.get_sku_detail.assert_not_called()
    finally:
        app.dependency_overrides.clear()
