"""T018: the synthetic export generator: deterministic, complete columns, every planted quirk, fictional data only."""

from __future__ import annotations

import csv
import importlib.util
import re
import sys
from pathlib import Path

import openpyxl
import pytest
from export_loader import formats
from export_loader.formats import fold
from generator.exports import generate_exports, write_exports

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_export_signatures.py"


@pytest.fixture(scope="module")
def exports():
    return generate_exports(seed=42)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def read_xlsx(path: Path) -> list[dict[str, str]]:
    ws = openpyxl.load_workbook(path, read_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    return [dict(zip(rows[0], ["" if c is None else str(c) for c in r], strict=False)) for r in rows[1:]]


def test_same_seed_gives_identical_bytes_and_other_seed_differs(tmp_path):
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    write_exports(a, seed=42)
    write_exports(b, seed=42)
    write_exports(c, seed=43)
    for name in ("inventario.csv", "movimientos.xlsx", "proveedores.csv"):
        assert (a / name).read_bytes() == (b / name).read_bytes()
        assert (a / name).read_bytes() != (c / name).read_bytes()


def test_files_carry_every_column_of_the_real_layouts(tmp_path):
    write_exports(tmp_path, seed=42)
    inv = read_csv(tmp_path / "inventario.csv")
    sup = read_csv(tmp_path / "proveedores.csv")
    mov = read_xlsx(tmp_path / "movimientos.xlsx")
    assert list(inv[0]) == formats.INVENTORY_HEADERS
    assert list(sup[0]) == formats.SUPPLIERS_HEADERS
    assert list(mov[0]) == formats.MOVEMENTS_HEADERS


def test_sizes_are_close_to_the_documented_fixture(tmp_path):
    write_exports(tmp_path, seed=42)
    assert 280 <= len(read_csv(tmp_path / "inventario.csv")) <= 330
    assert 380 <= len(read_xlsx(tmp_path / "movimientos.xlsx")) <= 460
    assert 22 <= len(read_csv(tmp_path / "proveedores.csv")) <= 30


def test_everything_is_visibly_synthetic(tmp_path):
    write_exports(tmp_path, seed=42)
    for row in read_csv(tmp_path / "inventario.csv"):
        assert row["SKU"].startswith("SYN-")
    for row in read_xlsx(tmp_path / "movimientos.xlsx"):
        assert row["SKU"].startswith("SYN-")
    for row in read_csv(tmp_path / "proveedores.csv"):
        assert int(row["ID"]) in formats.SYNTHETIC_SUPPLIER_IDS
        for col in ("Email General", "Email Directo", "Email Empresa"):
            assert not row[col] or row[col].endswith(".invalid")


def test_inventory_quirks(tmp_path):
    write_exports(tmp_path, seed=42)
    rows = read_csv(tmp_path / "inventario.csv")
    assert any(r["Tipo"] == "Servicio" for r in rows)
    skus = [r["SKU"] for r in rows]
    assert len(skus) != len(set(skus)), "a repeated SKU (second lot) is planted"
    assert any("\n" in r["Descripción"] for r in rows)
    assert any(r["Moneda"] != "EUR" for r in rows)
    assert any(r["Estado"] != "Activo" for r in rows)
    assert any(int(r["Stock Reservado"]) > int(r["Stock Total"]) for r in rows)
    assert any(int(r["Stock Total"]) < 0 for r in rows)
    assert any(float(r["Precio Coste (€)"]) == 0 for r in rows)
    assert any(float(r["Precio Coste (€)"]) > float(r["Precio Venta (€)"]) > 0 for r in rows)
    lots = [r for r in rows if r["Lote"]]
    assert 0 < len(lots) < 0.35 * len(rows)
    assert {r["Impuesto Incluido"] for r in rows} == {"Sí", "No"}
    assert {r["Tipo Impuesto"] for r in rows} >= {"IVA", "IVA10", "IVA21"}
    named = [r for r in rows if r["Proveedor"]]
    assert 0 < len(named) < 0.4 * len(rows), "most rows have no supplier, like the real export"


def test_movement_quirks(exports, tmp_path):
    write_exports(tmp_path, seed=42)
    rows = read_xlsx(tmp_path / "movimientos.xlsx")
    inv_skus = {r["SKU"] for r in read_csv(tmp_path / "inventario.csv")}
    assert all(re.fullmatch(r"\d{2}/\d{2}/\d{4}, \d{2}:\d{2}", r["Fecha"]) for r in rows)
    assert any(r["SKU"] not in inv_skus for r in rows), "an unknown SKU is planted"
    assert any((r["Caducidad"] and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", r["Caducidad"])) or re.fullmatch(r"\d{2}/\d{2}/\d{3}", r["Caducidad"] or "") for r in rows)
    assert any((fold(r["Tipo"]), fold(r["Motivo"])) not in formats.REASON_MAP for r in rows), "an unmapped reason is planted"
    assert any(not r["Lote"] for r in rows)
    mapped = {(fold(r["Tipo"]), fold(r["Motivo"])) for r in rows} & set(formats.REASON_MAP)
    assert len(mapped) == 8, "all eight mapped pairs appear"
    assert exports.truth["unknown_sku_rows"] >= 1


def test_supplier_quirks(tmp_path):
    write_exports(tmp_path, seed=42)
    rows = read_csv(tmp_path / "proveedores.csv")
    assert sum(r["Tipo Relación"] == "Cliente" for r in rows) >= 2
    names = [fold(r["Nombre Empresa"]).replace(".", "").replace(",", "") for r in rows]
    assert len(names) != len(set(names)), "duplicate-looking names (accents/case) are planted"
    assert any(r["Moneda Habitual"] == "USD" for r in rows)
    assert any(r["Condiciones Pago"] and not re.fullmatch(r"\d+( días)?", r["Condiciones Pago"]) for r in rows)
    assert any(r["Condiciones Pago"] in {"7 días", "30"} for r in rows)
    assert any(r["Notas"] for r in rows)
    assert any(not r["CIF"] for r in rows)
    assert {r["Tipo Fiscal"] for r in rows} >= {"nacional", "extranjero", "intracomunitario"}


def test_written_files_pass_the_repository_guard_when_placed_in_the_fixtures_folder(tmp_path):
    spec = importlib.util.spec_from_file_location("guard", SCRIPT)
    guard = importlib.util.module_from_spec(spec)
    sys.modules["guard"] = guard
    spec.loader.exec_module(guard)
    write_exports(tmp_path / "packages" / "testing" / "fixtures" / "exports", seed=42)
    assert guard.find_violations(tmp_path) == []
