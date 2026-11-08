"""T025: parsed exports → the Siweb mock's dataset (surrogate ids from the SKU map, stable movement ids, no free text)."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
from export_loader.formats import SURROGATE_BASE
from export_loader.parse_inventory import parse_inventory
from export_loader.parse_movements import parse_movements
from export_loader.sku_map import SkuMap
from export_loader.to_mock import build_dataset, dataset_from_json, dataset_to_json
from export_loader.validate_file import Limits
from fastapi.testclient import TestClient
from generator import Dataset, GenerationConfig
from generator.exports import write_exports
from siweb_mock.app import create_app
from siweb_mock.state import TOKEN

LIMITS = Limits()


@pytest.fixture(scope="module")
def parsed(tmp_path_factory):
    d = tmp_path_factory.mktemp("tm")
    write_exports(d, seed=42)
    inv = parse_inventory((d / "inventario.csv").read_bytes(), "inventario.csv", LIMITS)
    mov = parse_movements((d / "movimientos.xlsx").read_bytes(), "movimientos.xlsx", LIMITS, set(inv.items))
    return inv, mov


def build(parsed, tmp_path):
    inv, mov = parsed
    return build_dataset(inv, mov, SkuMap(tmp_path / "m.json"))


def test_variants_use_surrogate_ids_and_keep_the_sku(parsed, tmp_path):
    ds = build(parsed, tmp_path)
    inv, _ = parsed
    assert len(ds.variants) == len(inv.items) == len(ds.products)
    assert all(v["id"] >= SURROGATE_BASE and v["product_id"] == v["id"] for v in ds.variants)
    assert {v["sku"] for v in ds.variants} == {i.sku for i in inv.items.values()}


def test_ids_are_stable_across_builds(parsed, tmp_path):
    a = build(parsed, tmp_path)
    inv, mov = parsed
    b = build_dataset(inv, mov, SkuMap(tmp_path / "m.json"))
    assert [v["id"] for v in a.variants] == [v["id"] for v in b.variants]
    assert [m["id"] for m in a.movements] == [m["id"] for m in b.movements]


def test_price_is_the_tax_inclusive_selling_price_in_cents(parsed, tmp_path):
    ds = build(parsed, tmp_path)
    inv, _ = parsed
    by_sku = {v["sku"]: v for v in ds.variants}
    for item in list(inv.items.values())[:30]:
        assert by_sku[item.sku]["price_cents"] == int(item.pvp_gross * 100)
    assert isinstance(by_sku[next(iter(by_sku))]["price_cents"], int)


def test_services_are_flagged_and_have_no_stock(parsed, tmp_path):
    ds = build(parsed, tmp_path)
    services = [v for v in ds.variants if v.get("is_service")]
    assert len(services) == 3
    assert not {lot["variant_id"] for lot in ds.lots} & {v["id"] for v in services}


def test_lots_add_up_to_the_stock_total_and_skip_negative_stock(parsed, tmp_path):
    ds = build(parsed, tmp_path)
    inv, _ = parsed
    totals: dict[int, int] = {}
    for lot in ds.lots:
        totals[lot["variant_id"]] = totals.get(lot["variant_id"], 0) + lot["quantity"]
    ids = {v["sku"]: v["id"] for v in ds.variants}
    for item in inv.items.values():
        if item.kind == "physical" and item.total > 0:
            assert totals[ids[item.sku]] == item.total
        if item.total <= 0:
            assert ids[item.sku] not in totals
    assert all(lot["quantity"] > 0 for lot in ds.lots)


def test_warehouses_come_from_the_movements_and_are_stable(parsed, tmp_path):
    ds = build(parsed, tmp_path)
    assert [w["id"] for w in ds.warehouses] == [1, 2, 3] and all(w["name"].startswith("Almacen Sintetico") for w in ds.warehouses)


def test_movement_ids_are_unique_ascending_and_content_based(parsed, tmp_path):
    ds = build(parsed, tmp_path)
    ids = [m["id"] for m in ds.movements]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    times = [m["created_at"] for m in ds.movements]
    assert times == sorted(times)


def test_adding_newer_movements_keeps_old_ids(parsed, tmp_path):
    inv, mov = parsed
    old = build_dataset(inv, mov, SkuMap(tmp_path / "m.json"))
    from dataclasses import replace
    extra = replace(mov.movements[0], when=mov.movements[0].when.replace(year=2027), raw_date="01/01/2027, 10:00")
    mov2 = type(mov)([*mov.movements, extra], mov.report, mov.ok_rows + 1)
    new = build_dataset(inv, mov2, SkuMap(tmp_path / "m.json"))
    assert {m["id"] for m in old.movements} <= {m["id"] for m in new.movements}


def test_movement_payload_shape_and_privacy(parsed, tmp_path):
    ds = build(parsed, tmp_path)
    for m in ds.movements:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", m["created_at"])
        assert m["movement_type"] in {"in", "out"} and (m["quantity"] > 0) == (m["movement_type"] == "in")
        assert m["notes"] in {"", "nota"}
        assert m["unit_cost_cents"] is None
    assert any(m["reference_type"] == "ticket" and isinstance(m["reference_id"], int) for m in ds.movements if m["reason"] == "sale_shipment")
    assert any(m["reference_type"] == "purchase" for m in ds.movements if m["reason"] == "purchase_receipt")


def test_malformed_expiry_passes_through_as_raw_text(parsed, tmp_path):
    ds = build(parsed, tmp_path)
    raw = [m["expiry_date"] for m in ds.movements if m["expiry_date"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", m["expiry_date"])]
    assert sorted(raw) == ["30/08/027", "30/08/028"]


def test_json_round_trip_and_mock_load(parsed, tmp_path):
    ds = build(parsed, tmp_path)
    again = dataset_from_json(dataset_to_json(ds))
    assert again.variants == ds.variants and again.movements == ds.movements and again.lots == ds.lots
    app = create_app(Dataset(GenerationConfig(), [], [], [], {}, [], []))
    c = TestClient(app)
    assert c.post("/__mock__/load", json=dataset_to_json(ds)).json()["ok"] is True
    h = {"Authorization": f"Bearer {TOKEN}"}
    page = c.get("/api/public/inventory/variants", params={"limit": 200}, headers=h).json()
    assert page["pagination"]["total"] == len(ds.variants)
    assert c.get("/__mock__/health").json()["movements"] == len(ds.movements)
    mv = c.get("/api/public/inventory/movements", params={"limit": 200}, headers=h).json()
    assert mv["data"][0]["id"] == max(m["id"] for m in ds.movements)


def test_mock_load_is_refused_in_production(parsed, tmp_path, monkeypatch):
    monkeypatch.setenv("MMI_ENV", "prod")
    c = TestClient(create_app(Dataset(GenerationConfig(), [], [], [], {}, [], [])))
    assert c.post("/__mock__/load", json=dataset_to_json(build(parsed, tmp_path))).status_code == 403


def test_decimal_money_never_becomes_a_float(parsed, tmp_path):
    ds = build(parsed, tmp_path)
    assert all(isinstance(v["price_cents"], int) for v in ds.variants)
    assert Decimal("12.10") * 100 == 1210
