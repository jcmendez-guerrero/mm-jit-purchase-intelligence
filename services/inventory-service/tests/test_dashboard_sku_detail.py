"""Feature 014 (T025, US3): the SKU detail page data. Synthetic reference dataset (TOTALS.md); the SKU is the only identifier a caller supplies or receives."""

import json
from pathlib import Path

import jsonschema
import pytest
from conftest import auth
from reference_dataset import freeze_clock, seed_reference

SCHEMA = json.loads((Path(__file__).resolve().parents[3] / "packages" / "contracts" / "dto" / "dashboard_sku.v1.schema.json").read_text(encoding="utf-8"))


@pytest.fixture
def seeded(engine, monkeypatch):
    freeze_clock(monkeypatch)
    seed_reference(engine)
    return engine


def get(client, sku, role="buyer"):
    return client.get(f"/dashboard/skus/{sku}", headers=auth(role))


def test_a_buyer_gets_stock_coverage_demand_supplier_expiry_lots_and_cost(client, seeded):
    body = get(client, "SYN-001").json()
    assert body["sku"] == "SYN-001" and body["name"]
    assert {"stock", "coverage", "demand", "forecast", "supplier", "expiry_lots", "states"} <= body.keys()
    assert body["supplier"] == {"id": "sup-a"}
    bands = {lot["batch"]: lot["band"] for lot in body["expiry_lots"]}
    assert bands == {"L1": "later", "L2": "d0_30"}
    assert body["cost"]["value"] == "40.00" and body["cost"]["estimated"] is False


def test_every_role_gets_a_page_that_matches_the_contract_for_every_reference_product(client, seeded):
    for role in ("buyer", "viewer"):
        for sku in ("SYN-001", "SYN-002", "SYN-003", "SYN-004", "SYN-005"):
            jsonschema.validate(get(client, sku, role).json(), SCHEMA, cls=jsonschema.Draft202012Validator)


def test_the_cost_is_absent_not_hidden_for_a_viewer(client, seeded):
    body = get(client, "SYN-001", "viewer").json()
    text = json.dumps(body)
    assert "cost" not in body and "unit_cost" not in text and "40.00" not in text
    assert body["sku"] == "SYN-001" and len(body["expiry_lots"]) == 2


def test_no_internal_id_reaches_the_caller(client, seeded):
    text = json.dumps(get(client, "SYN-001").json())
    assert "variant_id" not in text and "external_id" not in text


def test_a_product_without_demand_or_with_an_estimated_cost_says_why(client, seeded):
    assert "no_demand_history" in get(client, "SYN-004").json()["states"]
    assert "cost_estimated" in get(client, "SYN-002").json()["states"]
    assert "no_cost" in get(client, "SYN-003").json()["states"]


def test_an_unknown_sku_is_not_found_and_leaks_nothing(client, seeded):
    r = get(client, "NOPE-1")
    assert r.status_code == 404 and r.json()["detail"] == "sku_not_found" and "SYN" not in r.text


def test_a_malformed_sku_is_refused(client, seeded):
    assert get(client, "bad sku;drop").status_code == 422
