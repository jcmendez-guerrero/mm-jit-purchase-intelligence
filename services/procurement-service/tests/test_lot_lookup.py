"""T049: the lot lookup when a request is built."""

import httpx
import pytest
from builders import FakeLots
from conftest import NOW, add_product, add_supplier
from costs.lot_lookup import HttpLotsSource, LotLookupError, fetch_lots
from costs.median_suggestion import request_median_write
from db.tables import cost_write_requests
from sqlalchemy import func, select


def test_retries_a_bounded_number_of_times_then_fails_visibly():
    sleeps = []
    ok = FakeLots([{"variant_id": 1, "lot": "L", "quantity": 1}], fail=2)
    assert fetch_lots(ok, [1], attempts=3, sleep=sleeps.append)[0]["lot"] == "L" and ok.calls == 3 and sleeps == [0.2, 0.4]
    down = FakeLots([], fail=99)
    with pytest.raises(LotLookupError) as e:
        fetch_lots(down, [1], attempts=3, sleep=lambda _s: None)
    assert e.value.code == "inventory_unavailable" and down.calls == 3


def test_an_unavailable_inventory_builds_no_request_and_uses_no_stale_stock(conn):
    sid = add_supplier(conn)
    add_product(conn, 1, 10)
    with pytest.raises(LotLookupError):
        request_median_write(conn, FakeLots([], fail=99), 10, sid, "receipt_matched", "system", NOW)
    assert conn.execute(select(func.count()).select_from(cost_write_requests)).scalar() == 0


def test_the_http_source_sends_the_scoped_token_and_the_variant_ids_and_hides_the_token():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(auth=request.headers["authorization"], ids=request.url.params["variant_ids"], path=request.url.path)
        return httpx.Response(200, json={"lots": [{"variant_id": 1, "lot": "L1", "quantity": 3}]})

    src = HttpLotsSource("http://inventory", "secret-abc", httpx.Client(transport=httpx.MockTransport(handler)))
    assert src.in_stock([1, 2]) == [{"variant_id": 1, "lot": "L1", "quantity": 3}]
    assert seen == {"auth": "Bearer secret-abc", "ids": "1,2", "path": "/lots/in-stock"} and "secret-abc" not in repr(src)


def test_http_errors_surface_as_the_visible_failure():
    src = HttpLotsSource("http://inventory", "t", httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))))
    with pytest.raises(LotLookupError):
        fetch_lots(src, [1], attempts=2, sleep=lambda _s: None)


def _app(engine, tmp_path, lots):
    from api import costs, proposals
    from fastapi.testclient import TestClient
    from mmi_common.auth import AuthError, Principal
    from mmi_common.service import create_service_app

    class V:
        def validate(self, token, required_roles=()):
            roles = {"viewer", "buyer"} if token == "buyer" else {"viewer"}  # noqa: S105 - test token name
            if not set(required_roles) <= roles:
                raise AuthError("forbidden", 403)
            return Principal(f"user-{token}", frozenset(roles), None)

    class Blob:
        def put(self, name, data):
            p = tmp_path / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            return p.as_uri()

    app = create_service_app("procurement-service", validator=V())
    app.include_router(costs.build_router(app))
    app.include_router(proposals.build_router(app))
    app.state.blob_writer, app.state.lots_source = Blob(), lots
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app)


def test_the_buyer_enters_an_opening_cost_then_requests_the_update_and_inventory_down_is_a_503(engine, tmp_path):
    from decimal import Decimal

    with engine.begin() as c:
        sid = add_supplier(c)
        add_product(c, 1, 10, vat=Decimal("21"))
    h = {"Authorization": "Bearer buyer"}
    entry = {"variant_id": 1, "supplier_id": sid, "lot": "opening", "amount": "100", "includes_recargo": False, "source": "buyer_entry"}
    api = _app(engine, tmp_path, FakeLots([]))
    assert api.post("/lot-costs", json=entry, headers={"Authorization": "Bearer viewer"}).status_code == 403
    r = api.post("/lot-costs", json=entry, headers=h)
    assert r.status_code == 201 and r.json()["unit_cost"] == "105.2000"
    assert api.post("/lot-costs", json={**entry, "source": "erp_movement"}, headers=h).status_code == 422
    assert api.post("/lot-costs", json={**entry, "amount": "-1"}, headers=h).status_code == 422
    assert api.post("/lot-costs", json={**entry, "supplier_id": "nope"}, headers=h).status_code == 422
    assert [x["lot"] for x in api.get(f"/lot-costs?variant_id=1&supplier_id={sid}", headers=h).json()] == ["opening"]
    made = api.post("/cost-updates", json={"product_id": 10, "supplier_id": sid}, headers=h)
    assert made.status_code == 201 and made.json()["status"] in ("pending_review", "pending_link")
    w = api.get("/cost-writes", headers=h).json()[0]
    assert w["median_cost"] == "105.20" and w["lots"][0]["lot"] == "opening"
    down = _app(engine, tmp_path, FakeLots([], fail=99))
    assert down.post("/cost-updates", json={"product_id": 10, "supplier_id": sid}, headers=h).json()["detail"] == "inventory_unavailable"
