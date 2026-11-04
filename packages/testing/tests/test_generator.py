"""T021: fixtures reproduce only aggregate ratios and contain no real-looking values."""

import re
from collections import Counter

import pytest
from generator import GenerationConfig, generate


@pytest.fixture(scope="module")
def data():
    return generate()


def test_deterministic_for_a_seed():
    a, b = generate(GenerationConfig(n_variants=200)), generate(GenerationConfig(n_variants=200))
    assert a.movements == b.movements
    assert generate(GenerationConfig(n_variants=200, seed=1)).movements != a.movements


def test_shape_matches_plan(data):
    assert len(data.variants) == 1000
    assert len(data.warehouses) == 3
    assert any(m["warehouse_id"] is None for m in data.movements)  # "unassigned" bucket
    assert {m["reason"] for m in data.movements} >= {"sale_shipment", "purchase_receipt", "adjustment_negative", "return_customer", "transfer_out", "initial_stock", "expiry"}
    ids = [m["id"] for m in data.movements]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)


def test_reason_mix_matches_aggregate_ratios(data):
    ms = [m for m in data.movements if m["reason"] != "initial_stock"]
    c = Counter(m["reason"] for m in ms)
    n = len(ms)
    assert 0.42 <= c["sale_shipment"] / n <= 0.58
    assert 0.32 <= c["purchase_receipt"] / n <= 0.48
    adjustments = (c["adjustment_negative"] + c["adjustment_positive"] + c["expiry"] + c["damage"] + c["theft"]) / n
    assert 0.06 <= adjustments <= 0.14
    assert (c["return_customer"] + c["transfer_out"]) / n < 0.04  # few returns, rare transfers


def test_demand_is_sparse(data):
    sales = [m for m in data.movements if m["reason"] == "sale_shipment"]
    assert 0.80 <= sum(1 for m in sales if m["quantity"] == -1) / len(sales) <= 0.92
    last_month = [m for m in data.movements if m["created_at"] >= "2026-10-04"]
    sold = Counter(m["variant_id"] for m in last_month if m["reason"] == "sale_shipment")
    assert 0.55 <= sum(1 for v in sold.values() if v == 1) / len(sold) <= 0.85
    moved = {m["variant_id"] for m in last_month}
    assert 0.10 <= len(moved) / len(data.variants) <= 0.40


def test_planted_defects_and_pre_cutover_expiry_notes(data):
    by_id = {m["id"]: m for m in data.movements}
    assert data.truth["malformed_expiry_ids"] and all(len(by_id[i]["expiry_date"].split("-")[0]) == 4 and by_id[i]["expiry_date"].startswith("202") for i in data.truth["malformed_expiry_ids"])
    assert all(by_id[i]["reference_number"] is None for i in data.truth["unreferenced_sale_ids"])
    pre = [m for m in data.movements if m["reason"] == "adjustment_negative" and m["created_at"] < "2026-09-19"]
    assert pre and not any(m["reason"] in ("expiry", "damage", "theft") and m["created_at"] < "2026-09-19" for m in data.movements)
    assert data.truth["stockout_days"]
    ms = [m for m in data.movements if m["reason"] != "initial_stock"]
    assert 0.05 <= sum(1 for m in ms if m["batch_number"] is None and m["reason"] == "purchase_receipt") / max(1, sum(1 for m in ms if m["reason"] == "purchase_receipt")) <= 0.12


def test_timestamps_are_offset_less_local_business_hours(data):
    for m in data.movements[:500]:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", m["created_at"])
        assert 8 <= int(m["created_at"][11:13]) <= 18


def test_no_real_looking_values(data):
    blob = repr((data.warehouses, data.products, data.variants, data.suppliers, data.movements))
    assert not re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", blob)  # no e-mail addresses
    assert all(p["name"].startswith("Producto Sintetico") for p in data.products)
    assert all(w["name"].startswith("Almacen Sintetico") for w in data.warehouses)
    assert all(v["sku"].startswith(("SYN-", "0000")) for v in data.variants)
    rows = [r for rs in data.suppliers.values() for r in rs]
    assert rows and all(r["supplier_name"].startswith("Proveedor Sintetico") for r in rows)
    assert all(re.fullmatch(r"X\d{8}Z", r["supplier_cif"]) for r in rows)  # clearly fake tax-ID shape
    assert any(r["purchase_cost_cents"] is None for r in rows)  # missing-cost cases exist
    assert any(not rs for rs in data.suppliers.values())        # products without suppliers exist


def test_free_text_notes_include_injection_probe(data):
    assert any("IGNORE PREVIOUS INSTRUCTIONS" in m["notes"] for m in data.movements)
