"""T072: price-list import validation, error list, CSV and Excel."""

import io
from decimal import Decimal

import pytest
from conftest import NOW, add_product, add_supplier
from costs import price_import as pi
from costs.directory import SqlProductDirectory
from costs.recargo import RecargoTable
from costs.rules import CostRules
from costs.store import current, history

D = Decimal
HEADER = "variant_id;cost;includes_recargo;pack_size;lead_time_days;min_order_qty"


def setup(conn):
    sid = add_supplier(conn)
    add_product(conn, 10, 1, vat=D("21"))
    add_product(conn, 20, 2, vat=D("10"))
    add_product(conn, 30, 3, vat=None)
    return sid


def run(conn, text, name="lista.csv"):
    rows = pi.read_rows(text.encode(), name)
    return pi.validate(rows, SqlProductDirectory(conn), RecargoTable())


def test_valid_file_computes_recargo_from_the_product_vat(conn):
    sid = setup(conn)
    res = run(conn, f"{HEADER}\n10;100,00;no;12;3;6\n20;50.00;si;;;\n")
    assert res.ok and len(res.rows) == 2
    net_row, gross_row = res.rows
    assert net_row.cost_with_recargo == D("105.2000") and net_row.cost_net == D("100.00") and net_row.entered_includes_recargo is False
    assert gross_row.cost_with_recargo == D("50.00") and gross_row.cost_net == D("49.3097") and gross_row.recargo_rate == D("0.014")
    assert (net_row.pack_size, net_row.lead_time_days, net_row.min_order_qty) == (12, 3, 6) and gross_row.pack_size is None
    assert pi.apply(conn, res, sid, "buyer-1", CostRules(), NOW) == 2
    stored = current(conn, 1, sid, 10)
    assert D(str(stored.cost_with_recargo)) == D("105.2000") and stored.source == "csv_price_list" and stored.variant_id == 10


def test_every_problem_is_reported_with_row_and_column_and_nothing_is_stored(conn):
    sid = setup(conn)
    text = f"{HEADER}\nabc;1;si;;;\n99;1;si;;;\n10;-3;si;;;\n10;4;talvez;;;\n20;x;si;;;\n30;5;no;;;\n20;5;si;0;;\n20;5;si;;-1;\n10;1;si;;;\n10;2;si;;;\n"
    res = run(conn, text)
    got = {(e.row, e.column, e.code) for e in res.errors}
    assert {(2, "variant_id", "not_an_integer"), (3, "variant_id", "unknown_variant"), (4, "cost", "negative"),
            (5, "includes_recargo", "must_be_si_or_no"), (6, "cost", "not_a_number"), (7, "includes_recargo", "vat_unknown_for_net_cost"),
            (8, "pack_size", "invalid_integer"), (9, "lead_time_days", "invalid_integer"), (11, "variant_id", "duplicate_of_row_4")} <= got
    assert pi.apply(conn, res, sid, "buyer-1", CostRules(), NOW) == 0 and history(conn, 1, sid, 10) == []


def test_a_net_cost_for_an_unknown_vat_is_rejected_but_a_gross_one_is_accepted(conn):
    setup(conn)
    assert run(conn, f"{HEADER}\n30;5;no;;;\n").errors[0].code == "vat_unknown_for_net_cost"
    ok = run(conn, f"{HEADER}\n30;5;si;;;\n")
    assert ok.ok and ok.rows[0].cost_net is None


@pytest.mark.parametrize("text,expected", [("1,25", "1.25"), ("1.25", "1.25"), ("1.234,56", "1234.56"), ("1,234.56", "1234.56"), (" 7 ", "7")])
def test_spanish_and_international_number_formats(text, expected):
    assert pi.parse_decimal(text) == D(expected)


@pytest.mark.parametrize("text", ["", "abc", "NaN", "Infinity", "1,2,3x"])
def test_bad_numbers_are_rejected(text):
    with pytest.raises(ValueError):
        pi.parse_decimal(text)


@pytest.mark.parametrize("data,name,code", [
    (b"a;b\n1;2\n", "x.csv", "template_mismatch"), (b"", "x.csv", "empty_file"), (b"x", "x.pdf", "unsupported_file_type"),
    (b"x", "x.xlsm", "macro_workbook_refused"), (b"\xff\xfe", "x.csv", "not_utf8"), (b"x" * 2_000_001, "x.csv", "file_too_large"),
    (b"not a zip", "x.xlsx", "unreadable_workbook"), (f"{HEADER};extra\n".encode(), "x.csv", "template_mismatch"),
])
def test_unusable_files_are_refused_with_a_code(data, name, code):
    with pytest.raises(pi.ImportFileError, match=code):
        pi.read_rows(data, name)


def test_comma_delimited_csv_and_bom_are_accepted():
    rows = pi.read_rows("﻿variant_id,cost,includes_recargo,pack_size,lead_time_days,min_order_qty\n10,1.5,si,,,\n".encode(), "x.csv")
    assert rows[0]["cost"] == "1.5" and rows[0]["_row"] == 2


def test_excel_files_use_the_same_template():
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(list(pi.TEMPLATE))
    ws.append([10, 100.5, "no", 12, 3, 6])
    ws.append([20, "2,5", "si", None, None, None])
    buf = io.BytesIO()
    wb.save(buf)
    rows = pi.read_rows(buf.getvalue(), "lista.xlsx")
    assert [r["variant_id"] for r in rows] == ["10", "20"] and rows[0]["cost"] == "100.5" and rows[1]["pack_size"] == ""


def test_row_limit(conn):
    body = HEADER + "\n" + "\n".join(f"{i};1;si;;;" for i in range(1, pi.MAX_ROWS + 2))
    with pytest.raises(pi.ImportFileError, match="too_many_rows"):
        pi.read_rows(body.encode(), "x.csv")
