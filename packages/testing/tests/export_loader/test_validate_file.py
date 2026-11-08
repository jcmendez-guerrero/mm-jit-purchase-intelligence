"""T011: file hardening before a single row is read (mirrors the seed-import cases)."""

from __future__ import annotations

import io
import zipfile

import openpyxl
import pytest
from export_loader import formats
from export_loader.validate_file import Limits, LoaderFileError, check_headers, check_row_count, detect_format

LIMITS = Limits(max_bytes=1_000_000, max_rows=1000, max_decompressed_bytes=5_000_000)


def xlsx_bytes(rows, formula=False) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    if formula:
        ws["B2"] = "=1+1"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def add_part(data: bytes, name: str, content: bytes = b"x") -> bytes:
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item.filename))
        dst.writestr(name, content)
    return out.getvalue()


def code(fn, *a):
    with pytest.raises(LoaderFileError) as exc:
        fn(*a)
    return exc.value.code


def test_csv_and_xlsx_are_accepted():
    assert detect_format("inventario.csv", b"SKU,Nombre\nA,B\n", LIMITS) == "csv"
    assert detect_format("movimientos.xlsx", xlsx_bytes([["a"], [1]]), LIMITS) == "xlsx"


def test_too_large_is_refused():
    assert code(detect_format, "a.csv", b"x" * 1_000_001, LIMITS) == "local_load_file_too_large"


@pytest.mark.parametrize("name", ["a.xlsm", "a.xls", "a.xlsb", "a.pdf", "a", "a.exe"])
def test_unsupported_extension_is_refused(name):
    assert code(detect_format, name, b"abc", LIMITS) == "local_load_type_not_allowed"


def test_extension_and_bytes_must_agree():
    assert code(detect_format, "a.xlsx", b"plain text", LIMITS) == "local_load_type_not_allowed"
    assert code(detect_format, "a.csv", zipfile.ZIP_STORED.to_bytes(1, "big") + b"PK\x03\x04", LIMITS) == "local_load_type_not_allowed"
    assert code(detect_format, "a.csv", b"abc\x00def", LIMITS) == "local_load_type_not_allowed"


def test_macro_part_is_refused():
    data = add_part(xlsx_bytes([["a"], [1]]), "xl/vbaProject.bin")
    assert code(detect_format, "a.xlsx", data, LIMITS) == "local_load_macros_or_links"


def test_external_link_is_refused():
    data = add_part(xlsx_bytes([["a"], [1]]), "xl/externalLinks/externalLink1.xml")
    assert code(detect_format, "a.xlsx", data, LIMITS) == "local_load_macros_or_links"


def test_formula_cell_is_refused():
    assert code(detect_format, "a.xlsx", xlsx_bytes([["a", "b"], [1, 2]], formula=True), LIMITS) == "local_load_macros_or_links"


def test_decompression_bomb_is_refused():
    big = xlsx_bytes([["a"], ["0" * 10]])
    data = add_part(big, "xl/media/bomb.bin", b"0" * 8_000_000)
    assert code(detect_format, "a.xlsx", data, LIMITS) == "local_load_file_too_large"


def test_damaged_package_is_refused():
    assert code(detect_format, "a.xlsx", b"PK\x03\x04garbage", LIMITS) == "local_load_type_not_allowed"


def test_row_limit():
    check_row_count(1000, LIMITS)
    assert code(check_row_count, 1001, LIMITS) == "local_load_too_many_rows"


def test_signature_mismatch_lists_missing_and_unexpected_columns():
    headers = [h for h in formats.MOVEMENTS_HEADERS if h != "Motivo"] + ["Extra"]
    with pytest.raises(LoaderFileError) as exc:
        check_headers("movements", headers)
    assert exc.value.code == "local_load_signature_mismatch"
    assert exc.value.missing == ["Motivo"]
    assert exc.value.unexpected == ["Extra"]
    assert "Motivo" in str(exc.value)


def test_matching_headers_pass_with_bom_and_spaces():
    check_headers("inventory", ["﻿SKU", *[f" {h} " for h in formats.INVENTORY_HEADERS[1:]]])
