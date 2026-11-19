"""Feature 014 (T090, FR-008a): inventory-service answers by SKU for the gateway; the machine route by `variant_id` stays; every row a person can see carries the SKU."""

import pytest
from conftest import auth
from reference_dataset import freeze_clock, seed_reference


@pytest.fixture
def seeded(engine, monkeypatch):
    freeze_clock(monkeypatch)
    seed_reference(engine)
    return engine


def test_the_sku_resolves_to_the_internal_id_for_the_gateway(client, seeded):
    res = client.get("/skus/SYN-001/variant", headers=auth("viewer"))
    assert res.status_code == 200
    body = res.json()
    assert body["sku"] == "SYN-001" and isinstance(body["id"], int) and body["name"]


def test_an_unknown_sku_is_not_found(client, seeded):
    res = client.get("/skus/NOPE-1/variant", headers=auth("viewer"))
    assert res.status_code == 404 and res.json()["detail"] == "sku_not_found"
    assert client.get("/skus/NOPE-1", headers=auth("viewer")).status_code == 404


def test_the_product_detail_by_sku_equals_the_one_by_internal_id(client, seeded):
    vid = client.get("/skus/SYN-001/variant", headers=auth("viewer")).json()["id"]
    by_sku = client.get("/skus/SYN-001", headers=auth("viewer"))
    by_id = client.get(f"/variants/{vid}", headers=auth("viewer"))
    assert by_sku.status_code == 200
    page, machine = by_sku.json(), by_id.json()
    assert machine["variant"]["id"] == vid                              # the machine route stays as it was
    assert "id" not in page["variant"] and "id" not in page["variant"]["product"]       # the browser's page has no internal id
    assert {**page, "variant": None} == {**machine, "variant": None} and page["variant"]["sku"] == "SYN-001"


def test_every_risk_row_carries_the_sku(client, seeded):
    rows = client.get("/risk", headers=auth("viewer")).json()
    assert rows and all(isinstance(r.get("sku"), str) and r["sku"] for r in rows)


def test_review_items_carry_the_sku(client, seeded):
    items = client.get("/review", headers=auth("buyer")).json()["items"]
    assert all("sku" in i for i in items)
