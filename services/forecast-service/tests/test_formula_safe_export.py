"""T103: output cells that a spreadsheet could execute are neutralised in CSV and XLSX; numbers stay numbers."""

import io

import pytest
from openpyxl import load_workbook
from seeds.template import neutralise, quarantine_csv, quarantine_xlsx, template_csv, template_xlsx

HOSTILE = ['=cmd|" /C calc"!A0', "+SUM(1;1)", "-2+3", "@SUM(1)", "\t=1", "\r=1"]


@pytest.mark.parametrize("text", HOSTILE)
def test_dangerous_text_is_made_inert(text):
    out = neutralise(text)
    assert out.startswith("'") and not out.startswith(("=", "+", "-", "@"))


def test_numbers_none_and_safe_text_are_untouched():
    assert neutralise(-3) == -3 and neutralise(2.5) == 2.5 and neutralise(None) is None and neutralise("Hoja sintética") == "Hoja sintética"


def test_the_quarantine_report_is_inert_in_csv_and_xlsx():
    rows = [(i + 2, t) for i, t in enumerate(HOSTILE)]
    import csv

    parsed = list(csv.reader(io.StringIO(quarantine_csv(rows).decode("utf-8-sig"), newline=""), delimiter=";"))[1:]
    assert len(parsed) == len(HOSTILE)
    for _n, cell in parsed:
        assert cell.startswith("'") and not cell.startswith(("=", "+", "-", "@"))
    ws = load_workbook(io.BytesIO(quarantine_xlsx(rows))).active
    for r in ws.iter_rows(min_row=2, values_only=True):
        assert str(r[1]).startswith("'") and isinstance(r[0], int)


def test_the_template_is_spanish_has_the_canonical_columns_and_made_up_values(): 
    text = template_csv().decode("utf-8-sig")
    assert text.splitlines()[0] == "ID de variante Siweb;SKU;Fecha;Cantidad;Almacén;Tipo de dato;Origen;Sintético/Real" and "9001" in text and "sintético" in text
    ws = load_workbook(io.BytesIO(template_xlsx())).active
    assert ws.title == "Plantilla de datos predictivos" and ws["A1"].value == "ID de variante Siweb" and ws["D2"].value == 2
