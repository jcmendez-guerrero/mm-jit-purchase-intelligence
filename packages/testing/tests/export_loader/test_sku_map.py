"""T014: SKU → surrogate id map: stable, case-insensitive, append-only, reserved range."""

import json

from export_loader.formats import SURROGATE_BASE
from export_loader.sku_map import SkuMap


def test_ids_start_in_the_reserved_range_and_increase(tmp_path):
    m = SkuMap(tmp_path / "sku-map.json")
    assert m.get_or_assign("SYN-000001") == SURROGATE_BASE
    assert m.get_or_assign("SYN-000002") == SURROGATE_BASE + 1


def test_same_sku_any_case_or_spacing_keeps_its_id(tmp_path):
    m = SkuMap(tmp_path / "sku-map.json")
    first = m.get_or_assign("SYN-000001")
    assert m.get_or_assign("  syn-000001 ") == first
    assert len(m) == 1


def test_map_persists_and_is_append_only(tmp_path):
    path = tmp_path / "sku-map.json"
    m = SkuMap(path)
    a = m.get_or_assign("SYN-A")
    m.save()
    m2 = SkuMap(path)
    assert m2.lookup("SYN-A") == a
    b = m2.get_or_assign("SYN-B")
    assert b == a + 1
    m2.save()
    assert SkuMap(path).lookup("SYN-A") == a


def test_lookup_of_unknown_sku_returns_none_and_assigns_nothing(tmp_path):
    m = SkuMap(tmp_path / "sku-map.json")
    assert m.lookup("SYN-X") is None
    assert len(m) == 0


def test_wipe_removes_the_file_and_restarts_numbering(tmp_path):
    path = tmp_path / "sku-map.json"
    m = SkuMap(path)
    m.get_or_assign("SYN-A")
    m.save()
    m.wipe()
    assert not path.exists()
    assert SkuMap(path).get_or_assign("SYN-Z") == SURROGATE_BASE


def test_file_holds_only_skus_and_integers(tmp_path):
    path = tmp_path / "sku-map.json"
    m = SkuMap(path)
    m.get_or_assign("SYN-A")
    m.save()
    data = json.loads(path.read_text())
    assert set(data) == {"next", "skus", "warehouses"} and all(isinstance(v, int) for v in data["skus"].values())


def test_reverse_lookup(tmp_path):
    m = SkuMap(tmp_path / "sku-map.json")
    i = m.get_or_assign("SYN-A")
    assert m.sku_for(i) == "SYN-A"
    assert m.sku_for(1) is None


def test_warehouse_ids_are_small_stable_and_persisted(tmp_path):
    path = tmp_path / "sku-map.json"
    m = SkuMap(path)
    assert m.warehouse_id("Almacen 1") == 1 and m.warehouse_id("  almacen   1 ") == 1 and m.warehouse_id("Almacen 2") == 2
    m.save()
    assert SkuMap(path).warehouse_id("Almacen 2") == 2 and SkuMap(path).warehouse_id("Almacen 3") == 3
