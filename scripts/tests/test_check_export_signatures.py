"""T009: the guard blocks real-shaped exports anywhere except the synthetic fixtures folder (and only if marked synthetic)."""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import openpyxl
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "check_export_signatures.py"
spec = importlib.util.spec_from_file_location("check_export_signatures", SCRIPT)
guard = importlib.util.module_from_spec(spec)
sys.modules["check_export_signatures"] = guard
spec.loader.exec_module(guard)

FIX = "packages/testing/fixtures/exports"


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def write_xlsx(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(path)


def inv_row(sku: str) -> list[str]:
    return [sku] + [""] * (len(guard.INVENTORY) - 1)


def mov_row(sku: str) -> list[str]:
    row = [""] * len(guard.MOVEMENTS)
    row[guard.MOVEMENTS.index("SKU")] = sku
    return row


def sup_row(ident: str) -> list[str]:
    return [ident] + [""] * (len(guard.SUPPLIERS) - 1)


def test_real_shaped_inventory_outside_fixtures_fails(tmp_path):
    write_csv(tmp_path / "docs" / "inv.csv", guard.INVENTORY, [inv_row("ABC-1")])
    assert guard.find_violations(tmp_path)


def test_real_shaped_movements_xlsx_outside_fixtures_fails(tmp_path):
    write_xlsx(tmp_path / "x" / "mov.xlsx", guard.MOVEMENTS, [mov_row("ABC-1")])
    assert guard.find_violations(tmp_path)


def test_real_shaped_suppliers_outside_fixtures_fails(tmp_path):
    write_csv(tmp_path / "sup.csv", guard.SUPPLIERS, [sup_row("123456")])
    assert guard.find_violations(tmp_path)


def test_synthetic_fixture_passes(tmp_path):
    write_csv(tmp_path / FIX / "inventory.csv", guard.INVENTORY, [inv_row("SYN-000001"), inv_row("SYN-000002")])
    write_xlsx(tmp_path / FIX / "movements.xlsx", guard.MOVEMENTS, [mov_row("SYN-000001")])
    write_csv(tmp_path / FIX / "suppliers.csv", guard.SUPPLIERS, [sup_row("9100001")])
    assert guard.find_violations(tmp_path) == []


@pytest.mark.parametrize("kind", ["inventory", "movements", "suppliers"])
def test_fixture_without_synthetic_marker_fails(tmp_path, kind):
    if kind == "inventory":
        write_csv(tmp_path / FIX / "inv.csv", guard.INVENTORY, [inv_row("SYN-000001"), inv_row("REAL-1")])
    elif kind == "movements":
        write_xlsx(tmp_path / FIX / "mov.xlsx", guard.MOVEMENTS, [mov_row("REAL-1")])
    else:
        write_csv(tmp_path / FIX / "sup.csv", guard.SUPPLIERS, [sup_row("123456")])
    assert guard.find_violations(tmp_path)


def test_unrelated_csv_and_xlsx_are_ignored(tmp_path):
    write_csv(tmp_path / "other.csv", ["a", "b"], [["1", "2"]])
    write_xlsx(tmp_path / "other.xlsx", ["a", "b"], [["1", "2"]])
    assert guard.find_violations(tmp_path) == []


def test_messages_never_contain_file_content(tmp_path):
    write_csv(tmp_path / "inv.csv", guard.INVENTORY, [inv_row("SECRET-SKU-XYZ")])
    assert all("SECRET-SKU-XYZ" not in v for v in guard.find_violations(tmp_path))


def test_private_folder_is_skipped_when_ignored_by_git(tmp_path):
    # outside a git repository the walk skips data/local-exports like git would (it is ignored by .gitignore)
    write_csv(tmp_path / "data" / "local-exports" / "inv.csv", guard.INVENTORY, [inv_row("ABC-1")])
    assert guard.find_violations(tmp_path) == []
