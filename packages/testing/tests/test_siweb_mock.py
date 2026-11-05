import pytest
from fastapi.testclient import TestClient
from generator import GenerationConfig, generate
from siweb_mock import TOKEN, MockConfig, create_app

AUTH = {"Authorization": f"Bearer {TOKEN}"}
BASE = "/api/public/inventory"


@pytest.fixture(scope="module")
def data():
    return generate(GenerationConfig(n_variants=200))


@pytest.fixture
def client(data):
    app = create_app(data, MockConfig())
    with TestClient(app, headers=AUTH) as c:
        c.mock = app.state.mock
        yield c


def test_auth_and_envelope(client):
    assert TestClient(client.app).get(f"{BASE}/warehouses").status_code == 401
    r = client.get(f"{BASE}/warehouses").json()
    assert r["success"] and len(r["data"]) == 3


def test_three_pagination_shapes(client):
    inv = client.get(f"{BASE}/variants?limit=50").json()
    assert set(inv["pagination"]) == {"page", "limit", "total", "pages"}
    pur = client.get("/api/public/purchases?limit=10").json()
    assert {"page", "limit", "totalPages"} <= set(pur) and "pagination" not in pur
    tic = client.get("/api/public/tickets?limit=10").json()
    assert "total" in tic and "pagination" not in tic and "totalPages" not in tic


def test_limit_above_200_rejected_and_products_active_only(client, data):
    assert client.get(f"{BASE}/movements?limit=201").status_code == 422
    data.products[0]["status"] = "inactive"
    try:
        ids = {p["id"] for p in client.get(f"{BASE}/products?limit=200").json()["data"]}
        assert data.products[0]["id"] not in ids
    finally:
        data.products[0]["status"] = "active"


def test_movements_newest_first_and_filters(client):
    rows = client.get(f"{BASE}/movements?limit=200").json()["data"]
    assert [m["id"] for m in rows] == sorted((m["id"] for m in rows), reverse=True)
    sales = client.get(f"{BASE}/movements?reason=sale_shipment&limit=200").json()["data"]
    assert sales and all(m["reason"] == "sale_shipment" for m in sales)
    assert all(m["notes"] is not None and "T" in m["created_at"] and "+" not in m["created_at"] for m in rows)


def test_mid_run_insert_shifts_pages_so_clients_must_dedupe(client):
    client.mock.config.insert_after_movement_requests = 1
    p1 = client.get(f"{BASE}/movements?limit=50&page=1").json()["data"]
    p2 = client.get(f"{BASE}/movements?limit=50&page=2").json()["data"]
    assert {m["id"] for m in p1} & {m["id"] for m in p2}, "new rows must push old ones across the page boundary"


def test_rate_limit_without_retry_after_by_default(client):
    client.mock.config.rate_limit_per_hour = 2
    client.mock.total_requests = 0
    codes = [client.get(f"{BASE}/warehouses").status_code for _ in range(4)]
    assert codes == [200, 200, 429, 429]
    assert "retry-after" not in client.get(f"{BASE}/warehouses").headers
    client.mock.config.send_retry_after = True
    assert client.get(f"{BASE}/warehouses").headers["retry-after"] == "60"


def test_missing_page_fails_once(client):
    client.mock.config.missing_pages = {2}
    assert client.get(f"{BASE}/movements?limit=50&page=2").status_code == 500
    assert client.get(f"{BASE}/movements?limit=50&page=2").status_code == 200


# ---------- supplier-cost PUT (T020) ----------


def _pair(client):
    for pid, rows in client.mock.suppliers.items():
        for r in rows:
            if r["purchase_cost_cents"] is not None and r["is_preferred"]:
                return pid, r
    raise AssertionError


def test_put_merges_and_changes_only_the_cost(client):
    pid, row = _pair(client)
    before = dict(row)
    r = client.put(f"{BASE}/products/{pid}/suppliers/{row['contact_id']}", json={"purchase_cost_cents": 1234.5})
    assert r.status_code == 200
    after = next(x for x in client.get(f"{BASE}/products/{pid}/suppliers").json()["data"] if x["contact_id"] == row["contact_id"])
    assert after["purchase_cost_cents"] == 1234.5                                        # fractional cents are accepted, as in the real API
    assert {k: v for k, v in after.items() if k != "purchase_cost_cents"} == {k: v for k, v in before.items() if k != "purchase_cost_cents"}


def test_lead_time_minimum_order_and_unknown_fields_are_ignored_like_the_real_api(client):
    pid, row = _pair(client)
    url = f"{BASE}/products/{pid}/suppliers/{row['contact_id']}"
    lead, moq = row["lead_time_days"], row["min_order_qty"]
    assert client.put(url, json={"purchase_cost_cents": 5, "lead_time_days": 99, "min_order_qty": 99, "bogus": 1}).status_code == 200
    assert (row["lead_time_days"], row["min_order_qty"]) == (lead, moq) and "bogus" not in row


def test_replace_mode_wipes_flags_unless_the_client_resends_them(client):
    client.mock.config.put_semantics = "replace"
    pid, row = _pair(client)
    url = f"{BASE}/products/{pid}/suppliers/{row['contact_id']}"
    client.put(url, json={"purchase_cost_cents": 9, "is_preferred": True, "supplier_reference": row["supplier_reference"]})
    assert row["is_preferred"] is True                                                    # read-modify-write survives
    client.put(url, json={"purchase_cost_cents": 1})
    assert row["is_preferred"] is False                                                   # a naive partial body would not


def test_put_creates_a_missing_link_like_the_real_api_unless_disabled(client):
    url = f"{BASE}/products/1/suppliers/987654"
    r = client.put(url, json={"purchase_cost_cents": 5})
    assert r.status_code == 200 and r.json()["data"]["contact_id"] == 987654 and r.json()["data"]["purchase_cost_cents"] == 5
    client.mock.config.allow_create = False
    assert client.put(f"{BASE}/products/1/suppliers/987655", json={"purchase_cost_cents": 5}).status_code == 404


def test_put_validation_and_injected_failures(client):
    pid, row = _pair(client)
    url = f"{BASE}/products/{pid}/suppliers/{row['contact_id']}"
    for bad in ({}, {"purchase_cost_cents": -5}, {"purchase_cost_cents": "abc"}, {"purchase_cost_cents": True}):
        r = client.put(url, json=bad)
        assert r.status_code == 400 and "mayor o igual que 0" in r.json()["message"]
    client.mock.config.fail_next_puts = 1
    assert client.put(url, json={"purchase_cost_cents": 5}).status_code == 503
    assert client.put(url, json={"purchase_cost_cents": 5}).status_code == 200


def test_request_log_records_writes(client):
    pid, row = _pair(client)
    client.get(f"{BASE}/warehouses")
    client.put(f"{BASE}/products/{pid}/suppliers/{row['contact_id']}", json={"purchase_cost_cents": 7})
    log = client.get("/__mock__/requests").json()
    assert [r["method"] for r in log].count("PUT") == 1
    assert len(client.mock.writes()) == 1
