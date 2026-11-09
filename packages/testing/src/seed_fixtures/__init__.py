"""Synthetic seed-import files, generated in memory for tests (including hostile ones). Synthetic data only."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from openpyxl import Workbook

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "seeds"
HEADER = ["SKU", "Fecha", "Cantidad", "Almacén", "Tipo de dato", "Origen", "Sintético/Real"]      # the template layout; products are identified by SKU (fictional EJ-9001 to EJ-9005)
XLSX_MAGIC = b"PK\x03\x04"


def static(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def valid_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(HEADER)
    for row in (
        ("EJ-9001", "2026-01-05", 2, None, "estimado", "Hoja sintética A", "sintético"),
        ("EJ-9002", "2026-01-12", 1, None, "previsión_manual", "Hoja sintética A", "sintético"),
        ("EJ-9003", "2026-03-02", 4, None, "observado_externo", "Hoja sintética B", "sintético"),
    ):
        ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def formula_xlsx() -> bytes:
    """A workbook whose cells hold formula text; a parser must read it as text and never evaluate it."""
    wb = Workbook()
    ws = wb.active
    ws.append(HEADER)
    ws.append(["EJ-9001", "2026-01-05", "=1+1", None, "estimado", '=HYPERLINK("http://example.invalid","x")', "sintético"])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def formula_csv() -> bytes:
    lines = [";".join(HEADER), 'EJ-9001;2026-01-05;2;;estimado;=cmd|" /C calc"!A0;sintético', "EJ-9002;2026-01-06;1;;estimado;+SUM(1;1);sintético", "EJ-9003;2026-01-07;1;;estimado;@SUM(1);sintético"]
    return ("\n".join(lines) + "\n").encode("utf-8")


def macro_workbook() -> bytes:
    """An XLSX package that carries a macro part (fake bytes, never executable); it must be refused."""
    src = zipfile.ZipFile(io.BytesIO(valid_xlsx()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in src.infolist():
            z.writestr(item, src.read(item.filename))
        z.writestr("xl/vbaProject.bin", b"SYNTHETIC-NOT-A-REAL-MACRO")
    return out.getvalue()


def wrong_signature_xlsx() -> bytes:
    """Plain text that claims to be a workbook: the content is not a ZIP package."""
    return static("valid.csv")


def oversized_csv(max_bytes: int) -> bytes:
    row = "EJ-9001;2026-01-05;1;;estimado;Hoja sintética A;sintético\n".encode()
    body = row * (max_bytes // len(row) + 2)
    return (";".join(HEADER) + "\n").encode() + body


def decompression_bomb_xlsx(uncompressed_mib: int = 64) -> bytes:
    """A small ZIP whose entry expands to a large size; limits on decompressed size must refuse it."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/worksheets/sheet1.xml", b"0" * (uncompressed_mib * 1024 * 1024))
    return out.getvalue()
