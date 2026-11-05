"""T103: exports use the Spanish locale profile (Spanish headers, semicolon CSV, comma decimals) and stay read-only."""

import io
from datetime import timedelta
from decimal import Decimal

import pytest
from approvals.workflow import decide, submit
from builders import flat_forecast, inputs, offer, terms, variant
from conftest import NOW, add_product, add_supplier
from db.tables import audit_events, proposals
from i18n import catalogue, t
from mmi_common.auth import Principal
from proposals.edit import edit_line
from proposals.export import HEADERS, ExportError, es_date, es_decimal, export_proposal
from proposals.generate import generate, store
from sqlalchemy import select

D = Decimal


class Users:
    def active_approvers(self):
        return {"approver-2"}


@pytest.fixture
def approved(conn):
    sa = add_supplier(conn, 1, "Proveedor Sintetico Uno")
    add_product(conn, 1, 10)
    from db.tables import product_refs
    from sqlalchemy import update

    conn.execute(update(product_refs).values(sku="SYN-000005", name="Producto Sintetico 5"))
    d = generate(inputs([variant(1, [offer(sa, "1.2345")], flat_forecast(1.0))], [terms(sa)]), 10)
    pid = store(conn, d, "buyer-1", "2026-W46", None, NOW)
    submit(conn, pid, "buyer-1", 1, Users(), NOW)
    decide(conn, pid, Principal("approver-2", frozenset({"approver"}), NOW - timedelta(minutes=1)), 1, now=NOW)
    return pid


def test_catalogue_holds_spanish_headers_for_every_column():
    assert next(t(h) for h in HEADERS) == "Proveedor" and [t(h) for h in HEADERS][4] == "Cantidad"
    assert all(catalogue()[h] for h in HEADERS)
    with pytest.raises(KeyError):
        t("export.nope")


def test_number_and_date_formats():
    assert es_decimal(D("1234.5")) == "1234,50" and es_decimal(D("1.23456"), 4) == "1,2346" and es_decimal(D("0")) == "0,00"
    assert es_date(None) == "" and es_date(__import__("datetime").date(2026, 11, 16)) == "16/11/2026"


def test_csv_is_semicolon_delimited_with_spanish_headers_and_comma_decimals(conn, approved):
    data = export_proposal(conn, approved, "csv", "buyer-1", now=NOW)
    assert data.startswith(b"\xef\xbb\xbf")
    lines = data.decode("utf-8-sig").splitlines()
    assert lines[0] == ";".join(t(h) for h in HEADERS)
    cells = lines[1].split(";")
    assert len(cells) == 8 and cells[0] == "Proveedor Sintetico Uno" and cells[1] == "SYN-000005" and cells[3] == "1"
    assert cells[5] == "1,2345" and "," in cells[6] and "." not in cells[5] + cells[6] and cells[7].count("/") == 2
    assert not any(c.isalpha() for c in lines[1].split(";")[5] + lines[1].split(";")[6])
    for h in ("Supplier", "Quantity", "Unit cost", "Line total", "Expected"):
        assert h not in lines[0]


def test_excel_has_spanish_headers_numeric_cells_and_euro_formats(conn, approved):
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(export_proposal(conn, approved, "xlsx", "buyer-1", now=NOW)))
    ws = wb.active
    assert ws.title == "Pedido" and [c.value for c in ws[1]] == [t(h) for h in HEADERS]
    row = ws[2]
    assert isinstance(row[4].value, int) and isinstance(row[5].value, float) and "€" in row[5].number_format and row[7].number_format == "DD/MM/YYYY"
    assert row[5].value == pytest.approx(1.2345) and row[6].value == pytest.approx(row[4].value * 1.2345, rel=1e-3)


def test_export_marks_the_proposal_exported_and_is_audited_but_writes_nothing_else(conn, approved):
    export_proposal(conn, approved, "csv", "buyer-1", now=NOW)
    assert conn.execute(select(proposals.c.status)).scalar_one() == "exported"
    last = conn.execute(select(audit_events).order_by(audit_events.c.id.desc())).first()
    assert (last.action, last.actor) == ("proposal.exported", "buyer-1")
    export_proposal(conn, approved, "xlsx", "buyer-1", now=NOW)                                   # exporting again is allowed


def test_only_an_approved_proposal_can_be_exported(conn):
    sa = add_supplier(conn)
    pid = store(conn, generate(inputs([variant(1, [offer(sa, "1")], flat_forecast(1.0))], [terms(sa)]), 10), "buyer-1", "2026-W46", None, NOW)
    with pytest.raises(ExportError) as e:
        export_proposal(conn, pid, "csv", "buyer-1", now=NOW)
    assert e.value.code == "proposal_not_approved"
    with pytest.raises(ExportError):
        export_proposal(conn, pid, "pdf", "buyer-1", now=NOW)
    with pytest.raises(ExportError):
        export_proposal(conn, "nope", "csv", "buyer-1", now=NOW)


def test_zero_quantity_lines_are_left_out_of_the_export(conn, approved):
    from db.tables import proposals as P
    from sqlalchemy import update

    conn.execute(update(P).values(status="draft"))
    edit_line(conn, approved, 1, 1, "buyer-3", qty=0, now=NOW)
    conn.execute(update(P).values(status="submitted"))
    from proposals.export import rows_for

    assert rows_for(conn, approved) == []
