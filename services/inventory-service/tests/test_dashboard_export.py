"""Feature 014 (T042, US5): the dashboard export is the screen in a file: same rows and totals, a header block, Spanish number format, safe cells, no prohibited fields.

Synthetic reference dataset (TOTALS.md): stock value 100.00 over four products (SYN-001 40.00, SYN-004 40.00, SYN-002 12.00, SYN-005 8.00).
"""

import csv
import io
from datetime import datetime

import pytest
from conftest import auth
from dashboard.drilldown import drilldown
from dashboard.export import MAX_ROWS, neutralise, number
from dashboard.filters import FilterSet
from dashboard.kpis import Filters, refresh_aggregates
from dashboard.series import build_charts
from db.tables import variants
from reference_dataset import NOW, TODAY, freeze_clock, seed_reference
from sqlalchemy import update


class FrozenNow(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


@pytest.fixture
def seeded(engine, monkeypatch):
    freeze_clock(monkeypatch)
    monkeypatch.setattr("dashboard.export.datetime", FrozenNow)        # the file is stamped, and its freshness measured, on the reference day
    seed_reference(engine)
    with engine.begin() as c:
        refresh_aggregates(c, TODAY, None, NOW)
    return engine


def export(client, role="buyer", **params):
    params = {"kind": "drilldown", "drill_kind": "inventory_value", **params}
    return client.get("/dashboard/export", params=params, headers=auth(role))


def parse(res):
    assert res.content.startswith(b"\xef\xbb\xbf"), "UTF-8 with a byte-order mark so a Spanish-locale spreadsheet reads the accents"
    return list(csv.reader(io.StringIO(res.content.decode("utf-8-sig"), newline=""), delimiter=";"))


def split(rows):
    """(header block, column header, data rows, total row or None)."""
    blank = rows.index([])
    head, body = rows[:blank], rows[blank + 1:]
    total = body[-1] if body and body[-1][0] == "Total" else None
    return head, body[0], body[1:-1] if total else body[1:], total


def test_a_drilldown_export_has_the_rows_and_the_total_of_the_screen(client, seeded):
    res = export(client)
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv") and 'attachment; filename="' in res.headers["content-disposition"]
    _head, columns, data, total = split(parse(res))
    with seeded.connect() as c:
        screen = drilldown(c, "inventory_value", TODAY, Filters(), limit=200)
    assert columns == ["SKU", "Producto", "Valor (EUR)"]
    assert [(r[0], r[2]) for r in data] == [(x["sku"], x["figure"].replace(".", ",")) for x in screen["rows"]]
    assert total == ["Total", "", screen["sum"].replace(".", ",")] and screen["sum"] == "100.00"


def test_the_header_block_names_the_report_filters_period_freshness_and_generation_time(client, seeded):
    res = export(client, supplier_id="sup-a", date_from="2026-10-01", date_to="2026-11-09")
    head, _cols, data, total = split(parse(res))
    keys = {r[0]: r[1:] for r in head}
    assert keys["Informe"] == ["Productos que forman el valor del inventario"]
    assert "Proveedor: sup-a" in keys["Filtros"][0] and keys["Periodo"] == ["2026-10-01 a 2026-11-09"]
    assert {"Frescura", "Generado (UTC)", "Generado (Madrid)"} <= keys.keys()
    assert [r[0] for r in data] == ["SYN-001", "SYN-005"] and total[2] == "42,00"           # the supplier filter reconciles with its card


def test_the_file_has_no_notes_tax_ids_or_internal_ids(client, seeded):
    res = export(client)
    _head, columns, data, _total = split(parse(res))
    assert columns == ["SKU", "Producto", "Valor (EUR)"]
    for forbidden in ("variant_id", "external_id", "supplier_cif", "nota", "note"):
        assert forbidden not in res.content.decode("utf-8-sig").lower()
    assert all(len(r) == 3 for r in data)


@pytest.mark.parametrize("hostile", ["=HYPERLINK(\"http://x\")", "+1+1", "-2+3", "@SUM(A1)", "\tcmd", "\rcmd"])
def test_a_text_cell_that_a_spreadsheet_could_run_is_kept_as_text(client, seeded, hostile):
    with seeded.begin() as c:
        c.execute(update(variants).where(variants.c.external_id == 1).values(name=hostile))
    _head, _cols, data, _total = split(parse(export(client)))
    name = next(r[1] for r in data if r[0] == "SYN-001")
    assert name == "'" + hostile and neutralise(hostile) == name


def test_text_is_neutralised_but_real_numbers_stay_numbers():
    assert neutralise("normal") == "normal" and neutralise("") == "" and neutralise(None) == ""
    assert number("-5.00") == "-5,00" and number("1234.5") == "1234,5" and number(7) == "7" and number(None) == ""


def test_a_chart_export_has_the_rows_of_the_chart_in_spanish(client, seeded):
    res = export(client, kind="chart", chart="expiry_bands")
    head, columns, data, total = split(parse(res))
    with seeded.connect() as c:
        chart = build_charts(c, ["expiry_bands"], TODAY, FilterSet.parse(TODAY), None, True)[0]
    assert columns == ["Tramo", "Productos", "Valor (EUR)"] and total is None
    assert [[r[0], r[1], r[2]] for r in data] == [["Caducado", "0", "0,00"], ["0 a 30 días", "1", "20,00"], ["31 a 60 días", "1", "40,00"]]
    assert len(data) == len(chart["rows"]) and {r[0]: r[1:] for r in head}["Informe"] == ["Valor que caduca por tramo"]


def test_a_cards_export_lists_the_indicators_with_their_state(client, seeded):
    head, columns, data, _total = split(parse(export(client, kind="cards")))
    assert columns == ["Indicador", "Valor", "Unidad", "Estado"]
    stock = next(r for r in data if r[0] == "Valor del stock")
    assert stock[1:] == ["100,00", "EUR", "Correcto"] and len(data) == 6                      # capital, budget and WAPE/bias depend on other services
    assert any(r[0] == "Fuera de este archivo" for r in head)


def test_a_viewer_is_refused_and_a_bad_request_is_a_clear_error(client, seeded):
    assert export(client, "viewer").status_code == 403
    assert client.get("/dashboard/export", params={"kind": "tabloid"}, headers=auth("buyer")).status_code == 422
    assert client.get("/dashboard/export", params={"kind": "chart", "chart": "nope"}, headers=auth("buyer")).status_code == 422
    xlsx = export(client, format="xlsx")
    assert xlsx.status_code == 400 and xlsx.json()["detail"] == "format_unsupported"


def test_a_result_above_the_limit_is_refused_not_cut_off(client, seeded, monkeypatch):
    import dashboard.export as mod

    monkeypatch.setattr(mod, "MAX_ROWS", 2)
    res = export(client)
    assert res.status_code == 413 and res.json()["detail"] == "export_too_large"
    assert MAX_ROWS >= 1000                                                   # the real limit is generous: a screen's worth of products fits


def test_two_exports_of_the_same_view_have_the_same_rows(client, seeded):
    assert split(parse(export(client)))[2:] == split(parse(export(client)))[2:]
