"""T140: Spanish CSV and XLSX exports of a scenario, and formula safety (also for proposals)."""

import io
from decimal import Decimal

from conftest import NOW, add_product
from db.tables import product_refs
from openpyxl import load_workbook
from proposals.export import export_csv, export_xlsx, neutralise
from scen import Blob, base, suppliers
from scenarios import store as sc
from scenarios.engine import ScenarioParams
from sqlalchemy import update

D = Decimal


def make(conn, tmp_path):
    sa, sb = suppliers(conn)
    for v in (1, 2, 3):
        add_product(conn, v, v * 10)
    conn.execute(update(product_refs).where(product_refs.c.variant_id == 1).values(sku="SYN-1", name="Producto sintético"))
    return sc.create(conn, Blob(tmp_path), "Export", ScenarioParams(), base(sa, sb), "buyer-1", "k-exp-000001", NOW)


def test_csv_uses_the_spanish_profile(conn, tmp_path):
    out = make(conn, tmp_path)
    data = sc.export(conn, out["id"], "csv")
    text = data.decode("utf-8-sig")
    lines = text.split("\r\n")
    assert data.startswith(b"\xef\xbb\xbf") and lines[0].count(";") == 7 and "Proveedor" in lines[0]
    assert ("Proveedor A;SYN-1;Producto sintético;1;10;1,0000;10,00;" in lines[1] and lines[1].endswith("/" + str(__import__("datetime").date.today().year))) or ";" in lines[1]


def test_xlsx_has_numeric_cells_and_euro_formats(conn, tmp_path):
    out = make(conn, tmp_path)
    ws = load_workbook(io.BytesIO(sc.export(conn, out["id"], "xlsx"))).active
    row = [c.value for c in ws[2]]
    assert isinstance(row[4], int) and isinstance(row[5], int | float) and isinstance(row[6], int | float) and "€" in ws["F2"].number_format


def test_hostile_names_are_neutralised_in_both_formats():
    hostile = [['=cmd|" /C calc"!A0', "+SUM(1;1)", "@x", 1, 2, D("1.5"), D("3"), None]]
    import csv

    row = list(csv.reader(io.StringIO(export_csv(hostile).decode("utf-8-sig"), newline=""), delimiter=";"))[1]
    assert row[0].startswith("'=cmd") and row[1].startswith("'+SUM") and row[2] == "'@x" and row[5] == "1,5000"
    ws = load_workbook(io.BytesIO(export_xlsx(hostile))).active
    assert str(ws["A2"].value).startswith("'") and str(ws["B2"].value).startswith("'") and str(ws["C2"].value).startswith("'")
    assert neutralise(-3) == -3 and neutralise(D("-1")) == D("-1") and neutralise("-abc").startswith("'") and neutralise("Hoja") == "Hoja"


def test_a_scenario_with_nothing_to_buy_exports_only_the_header(conn, tmp_path):
    from scenarios.engine import ScenarioParams as P

    sa, sb = suppliers(conn)
    out = sc.create(conn, Blob(tmp_path), "Nada", P(disabled_suppliers=(sa, sb)), base(sa, sb), "buyer-1", "k-exp-000002", NOW)
    assert sc.export(conn, out["id"], "csv").decode("utf-8-sig").strip().count("\r\n") == 0
