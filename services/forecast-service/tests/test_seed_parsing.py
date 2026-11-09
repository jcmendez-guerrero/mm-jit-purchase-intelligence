"""T098: CSV and XLSX parsing; formulas are never evaluated."""

import io

import pytest
import seed_fixtures as sf
from openpyxl import Workbook
from seeds.parsers import parse_csv, parse_xlsx
from seeds.storage import SeedFileError
from upload_settings import ParseLimits

L = ParseLimits()


def test_csv_semicolon_utf8_with_spanish_headers():
    headers, rows = parse_csv(sf.static("valid.csv"), L)
    assert headers[0] == "SKU" and rows[0]["SKU"] == "EJ-9001" and rows[0]["Cantidad"] == "2" and rows[0]["Origen"] == "Hoja sintética A"


def test_csv_delimiters_encodings_and_blank_lines():
    assert parse_csv(b"a,b\n1,2\n\n3,4\n", L)[1] == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
    assert parse_csv(b"a\tb\n1\t2\n", L)[1] == [{"a": "1", "b": "2"}]
    assert parse_csv("a;b\nñ;2\n".encode("cp1252"), L)[1][0]["a"] == "ñ"
    assert parse_csv("﻿a;b\n1;2\n".encode(), L)[0] == ["a", "b"]


def test_csv_limits_on_rows_and_columns():
    with pytest.raises(SeedFileError) as e:
        parse_csv(b"a\n" + b"1\n" * 5, ParseLimits(max_rows=3))
    assert e.value.code == "import_too_many_rows"
    with pytest.raises(SeedFileError):
        parse_csv(b",".join(b"c%d" % i for i in range(40)) + b"\n", L)
    with pytest.raises(SeedFileError) as e2:
        parse_csv(b"", L)
    assert e2.value.code == "import_missing_column"


def test_xlsx_first_sheet_only_and_dates_and_numbers_as_text():
    headers, rows = parse_xlsx(sf.valid_xlsx(), L)
    assert headers == sf.HEADER and len(rows) == 3 and rows[0]["SKU"] == "EJ-9001" and rows[2]["Tipo de dato"] == "observado_externo"


def test_xlsx_with_several_sheets_reads_only_the_first_and_enforces_the_sheet_limit():
    wb = Workbook()
    wb.active.append(["a"])
    wb.active.append([1])
    for i in range(3):
        wb.create_sheet(f"s{i}").append(["zz", 9])
    buf = io.BytesIO()
    wb.save(buf)
    assert parse_xlsx(buf.getvalue(), ParseLimits(max_sheets=5))[1] == [{"a": "1"}]
    with pytest.raises(SeedFileError):
        parse_xlsx(buf.getvalue(), ParseLimits(max_sheets=2))


def test_formulas_are_never_evaluated_they_stay_text_or_empty():
    _, rows = parse_xlsx(sf.formula_xlsx(), L)
    assert rows[0]["Cantidad"] in ("=1+1", "")                  # stored formula text or no cached value, never "2"
    assert "HYPERLINK" in rows[0]["Origen"] or rows[0]["Origen"] == ""
    _, csv_rows = parse_csv(sf.formula_csv(), L)
    assert csv_rows[0]["Origen"].startswith("=cmd") and csv_rows[1]["Origen"].startswith("+SUM")           # read as inert text


def test_unreadable_workbooks_are_refused_not_crashed():
    with pytest.raises(SeedFileError):
        parse_xlsx(b"PK\x03\x04garbage", L)
