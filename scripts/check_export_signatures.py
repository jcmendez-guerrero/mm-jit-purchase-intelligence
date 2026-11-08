#!/usr/bin/env python3
"""Block real-shaped Siweb UI exports from entering the repository (AGENTS.md rule 7a, constitution Principle II).

A CSV or XLSX whose header row contains every column of one of the three export layouts (inventory, movements,
suppliers) is allowed only under ``packages/testing/fixtures/exports/`` and only when it is visibly synthetic:
every SKU starts with ``SYN-`` and every supplier ``ID`` lies in the reserved synthetic range. Messages name the file
and the reason, never row content.

Usage: ``python scripts/check_export_signatures.py [--root DIR]``. Exit code 1 when a violation is found.
Dependency-free on purpose (runs in pre-commit and CI without installing the project).
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import zipfile
from collections.abc import Iterator
from pathlib import Path
from xml.etree import ElementTree as ET

INVENTORY = [
    "SKU", "Nombre", "Descripción", "Categoría", "Marca", "Proveedor", "Tipo", "Unidad de Medida", "Categoría Unidad",
    "Precio Venta (€)", "Precio Coste (€)", "Tipo Impuesto", "Tasa Impuesto (%)", "Impuesto Incluido", "Stock Disponible",
    "Stock Reservado", "Stock Total", "Punto de Reorden", "Stock Objetivo", "Moneda", "Estado", "Lote",
]
MOVEMENTS = ["Fecha", "Producto", "SKU", "Almacén", "Ubicación", "Lote", "Caducidad", "Tipo", "Motivo", "Cantidad", "Notas", "Referencia"]
SUPPLIERS = [
    "ID", "Nombre Empresa", "CIF", "Tipo Fiscal", "Sector", "Dirección", "Ciudad", "Provincia", "Código Postal", "País",
    "Teléfono Principal", "Email General", "Página Web", "Nombre Contacto", "Apellidos Contacto", "Cargo", "Teléfono Directo",
    "Email Directo", "LinkedIn", "Tipo Relación", "Categoría", "Fecha Alta", "Último Contacto", "Condiciones Pago", "Métodos Pago",
    "Moneda Habitual", "Email Empresa", "Email Personal", "Teléfono Emergencia", "Notas", "Nombre Facturación",
    "Dirección Facturación", "Ciudad Facturación", "Código Postal Facturación", "Provincia Facturación", "País Facturación",
    "Banco", "IBAN", "SWIFT", "Fecha Creación", "Fecha Actualización",
]
SIGNATURES = {"inventory": INVENTORY, "movements": MOVEMENTS, "suppliers": SUPPLIERS}
FIXTURES = "packages/testing/fixtures/exports"
SYNTHETIC_PREFIX = "SYN-"
SYNTHETIC_SUPPLIER_IDS = range(9_100_000, 9_200_000)
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".hypothesis", ".pytest_cache", ".ruff_cache"}
PRIVATE_PREFIX = ("data", "local-exports")
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx_rows(path: Path) -> Iterator[list[str]]:
    """Rows of the first sheet as lists of strings (no third-party dependency)."""
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))  # noqa: S314 - header detection on repository files only
            for si in root.findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        sheet = next((n for n in sorted(zf.namelist()) if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")), None)
        if sheet is None:
            return
        with zf.open(sheet) as fh:
            for _, el in ET.iterparse(fh):  # noqa: S314 - header detection on repository files only
                if el.tag != f"{{{NS['m']}}}row":
                    continue
                cells: dict[int, str] = {}
                for c in el.findall("m:c", NS):
                    t = c.get("t")
                    v = c.find("m:v", NS)
                    if t == "s" and v is not None:
                        val = shared[int(v.text)]
                    elif t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                    else:
                        val = v.text if v is not None and v.text is not None else ""
                    cells[_col_index(c.get("r"))] = val
                yield [cells.get(i, "") for i in range(max(cells) + 1)] if cells else []
                el.clear()


def _csv_rows(path: Path) -> Iterator[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as fh:
        yield from csv.reader(fh)


def _signature_of(header: list[str]) -> str | None:
    cols = {h.strip() for h in header}
    for kind, sig in SIGNATURES.items():
        if set(sig) <= cols:
            return kind
    return None


def _rows(path: Path) -> Iterator[list[str]]:
    return read_xlsx_rows(path) if path.suffix.lower() == ".xlsx" else _csv_rows(path)


def _check_synthetic(path: Path, kind: str) -> str | None:
    rows = _rows(path)
    header = [h.strip() for h in next(rows)]
    key = "ID" if kind == "suppliers" else "SKU"
    idx = header.index(key)
    for n, row in enumerate(rows, start=2):
        val = (row[idx] if idx < len(row) else "").strip()
        if not val:
            continue
        if kind == "suppliers":
            if not (val.isdigit() and int(val) in SYNTHETIC_SUPPLIER_IDS):
                return f"row {n}: supplier ID outside the synthetic range"
        elif not val.startswith(SYNTHETIC_PREFIX):
            return f"row {n}: {key} is not marked synthetic ({SYNTHETIC_PREFIX}…)"
    return None


def candidate_files(root: Path) -> list[Path]:
    try:
        out = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],  # noqa: S607
            capture_output=True, check=True, text=True,
        ).stdout
        files = [root / p for p in out.split("\0") if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        files = []
        for p in root.rglob("*"):
            rel = p.relative_to(root).parts
            if p.is_file() and not (set(rel) & SKIP_DIRS) and rel[:2] != PRIVATE_PREFIX:
                files.append(p)
    return [p for p in files if p.suffix.lower() in {".csv", ".xlsx"} and p.is_file()]


def find_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for path in candidate_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            header = next(_rows(path), [])
        except (OSError, zipfile.BadZipFile, ET.ParseError, StopIteration):
            continue
        kind = _signature_of(header)
        if kind is None:
            continue
        if not rel.startswith(FIXTURES + "/"):
            violations.append(f"{rel}: {kind} export layout outside {FIXTURES}/ (real exports must stay in data/local-exports)")
            continue
        reason = _check_synthetic(path, kind)
        if reason:
            violations.append(f"{rel}: {kind} fixture is not visibly synthetic ({reason})")
    return violations


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    found = find_violations(Path(args.root).resolve())
    for v in found:
        print(f"BLOCKED {v}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
