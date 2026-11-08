"""T024: movements XLSX parsing: text dates kept raw, reason mapping, unknown SKU, sign checks, notes reduced to a flag."""

from __future__ import annotations

import io
from datetime import datetime

import openpyxl
import pytest
from export_loader import formats
from export_loader.parse_inventory import parse_inventory, sku_key
from export_loader.parse_movements import parse_movements
from export_loader.validate_file import Limits, LoaderFileError
from generator.exports import write_exports

LIMITS = Limits()


@pytest.fixture(scope="module")
def parsed(tmp_path_factory):
    d = tmp_path_factory.mktemp("mov")
    data = write_exports(d, seed=42)
    inv = parse_inventory((d / "inventario.csv").read_bytes(), "inventario.csv", LIMITS)
    out = parse_movements((d / "movimientos.xlsx").read_bytes(), "movimientos.xlsx", LIMITS, set(inv.items))
    # movements of a product whose inventory row was quarantined (the non-EUR one) are unknown too
    quarantined = {sku_key(r["SKU"]) for r in data.inventory if r["Moneda"] != "EUR"}
    extra = sum(1 for m in data.movements if sku_key(m["SKU"]) in quarantined)
    return out, {**data.truth, "extra_unknown": extra}


def xlsx(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(formats.MOVEMENTS_HEADERS)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def mrow(fecha="07/11/2026, 13:31", sku="SYN-1", almacen="Almacen 1", lote="", cad="", tipo="Salida", motivo="Envío de venta", cant=-1, notas="", ref="SYN-2026-000001"):
    return [fecha, "Producto", sku, almacen, "", lote, cad, tipo, motivo, cant, notas, ref]


def one(row, known=("syn-1",)):
    return parse_movements(xlsx([row]), "m.xlsx", LIMITS, set(known))


def test_every_row_is_accounted_for(parsed):
    out, _ = parsed
    assert out.ok_rows + out.report.quarantined == out.report.rows and out.report.excluded == 0 and out.report.services == 0


def test_planted_quirks_are_counted(parsed):
    out, truth = parsed
    codes = [r["code"] for r in out.report.reviews]
    assert codes.count("unknown_sku") == truth["unknown_sku_rows"] + truth["extra_unknown"]
    assert codes.count("unmapped_reason") == truth["unmapped_reason_rows"]
    assert codes.count("sign_mismatch") == truth["sign_mismatch_rows"]
    assert out.report.quarantined == 5 + truth["extra_unknown"]
    assert sum(1 for m in out.movements if not m.expiry_valid) == truth["bad_expiry_rows"]


def test_text_date_is_parsed_and_the_raw_text_is_kept():
    m = one(mrow()).movements[0]
    assert m.when == datetime(2026, 11, 7, 13, 31) and m.raw_date == "07/11/2026, 13:31"  # noqa: DTZ001 - local, offset-less time on purpose


def test_excel_datetime_cells_are_read_too():
    m = one(mrow(fecha=datetime(2026, 7, 1, 10, 24))).movements[0]  # noqa: DTZ001
    assert m.when == datetime(2026, 7, 1, 10, 24)  # noqa: DTZ001 - local, offset-less time on purpose


def test_invalid_dates_are_quarantined():
    out = one(mrow(fecha="2026-11-07"))
    assert out.report.quarantined == 1 and out.report.reviews[0]["code"] == "invalid_date"
    assert one(mrow(fecha="31/02/2026, 10:00")).report.quarantined == 1


@pytest.mark.parametrize(("tipo", "motivo", "qty", "reason"), [
    ("Entrada", "Recepción de compra", 5, "purchase_receipt"), ("Salida", "Envío de venta", -1, "sale_shipment"),
    ("Entrada", "Devolución de cliente", 1, "return_customer"), ("Ajuste", "Ajuste negativo", -2, "adjustment_negative"),
    ("Ajuste", "Ajuste positivo", 2, "adjustment_positive"), ("Entrada", "Stock inicial", 10, "initial_stock"),
    ("Transferencia", "Entrada por transferencia", 1, "transfer_in"), ("Transferencia", "Salida por transferencia", -1, "transfer_out"),
    ("  ENTRADA ", "recepcion de compra", 5, "purchase_receipt"),
])
def test_reasons_are_mapped(tipo, motivo, qty, reason):
    assert one(mrow(tipo=tipo, motivo=motivo, cant=qty)).movements[0].reason == reason


def test_unmapped_reason_is_quarantined_not_guessed():
    out = one(mrow(tipo="Salida", motivo="Rotura"))
    assert out.report.quarantined == 1 and out.report.reviews[0]["code"] == "unmapped_reason" and not out.movements


def test_unknown_sku_is_quarantined():
    out = one(mrow(sku="SYN-404"))
    assert out.report.reviews[0]["code"] == "unknown_sku" and not out.movements


def test_sku_matching_ignores_case_and_spaces():
    assert one(mrow(sku=" syn-1 ")).movements[0].sku == "syn-1"


def test_sign_must_match_the_reason():
    assert one(mrow(cant=3)).report.reviews[0]["code"] == "sign_mismatch"
    assert one(mrow(cant=0)).report.reviews[0]["code"] == "zero_quantity"
    assert one(mrow(cant=1.5)).report.reviews[0]["code"] == "non_integer_quantity"


def test_malformed_expiry_is_passed_through_as_raw_text_for_the_platform_to_quarantine():
    out = one(mrow(tipo="Entrada", motivo="Recepción de compra", cant=6, lote="L1", cad="30/08/027"))
    m = out.movements[0]
    assert out.report.quarantined == 0 and m.expiry_iso is None and m.expiry_raw == "30/08/027" and not m.expiry_valid


def test_valid_expiry_becomes_iso():
    m = one(mrow(tipo="Entrada", motivo="Recepción de compra", cant=6, lote="L1", cad="30/08/2027")).movements[0]
    assert m.expiry_iso == "2027-08-30" and m.expiry_valid


def test_empty_lot_and_warehouse_are_kept_as_none():
    m = one(mrow(almacen="", lote="")).movements[0]
    assert m.batch is None and m.warehouse is None


def test_notes_are_reduced_to_a_flag():
    m = one(mrow(notas="texto libre privado")).movements[0]
    assert m.has_note and "texto libre privado" not in repr(m)
    assert not one(mrow(notas="")).movements[0].has_note


def test_wrong_headers_are_rejected():
    with pytest.raises(LoaderFileError) as exc:
        parse_movements(b"SKU,Nombre\nA,B\n", "m.csv", LIMITS, set())
    assert exc.value.code == "local_load_signature_mismatch"


def test_sku_key_is_shared_with_the_inventory_parser():
    assert sku_key(" SYN-1 ") == "syn-1"
