"""T023: inventory CSV parsing: SKU identity, Spanish numbers, tax interpretation, services, flags, privacy."""

from __future__ import annotations

from decimal import Decimal

import pytest
from export_loader import formats
from export_loader.parse_inventory import parse_inventory
from export_loader.validate_file import Limits, LoaderFileError
from generator.exports import write_exports

LIMITS = Limits()


@pytest.fixture(scope="module")
def parsed(tmp_path_factory):
    d = tmp_path_factory.mktemp("inv")
    truth = write_exports(d, seed=42).truth
    out = parse_inventory((d / "inventario.csv").read_bytes(), "inventario.csv", LIMITS)
    return out, truth


def csv_bytes(rows: list[list[str]]) -> bytes:
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(formats.INVENTORY_HEADERS)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def row(**kw) -> list[str]:
    base = {"SKU": "SYN-1", "Nombre": "N", "Descripción": "", "Categoría": "C", "Marca": "M", "Proveedor": "", "Tipo": "Físico",
            "Unidad de Medida": "unidad", "Categoría Unidad": "count", "Precio Venta (€)": "10.00", "Precio Coste (€)": "5.00",
            "Tipo Impuesto": "IVA10", "Tasa Impuesto (%)": "10", "Impuesto Incluido": "No", "Stock Disponible": "3", "Stock Reservado": "1",
            "Stock Total": "4", "Punto de Reorden": "1", "Stock Objetivo": "6", "Moneda": "EUR", "Estado": "Activo", "Lote": ""}
    base.update(kw)
    return [base[h] for h in formats.INVENTORY_HEADERS]


def test_every_row_is_accounted_for(parsed):
    out, truth = parsed
    r = out.report
    assert out.ok_rows + r.quarantined + r.excluded + r.services == r.rows
    assert r.services == truth["service_rows"]


def test_repeated_sku_is_one_item_with_two_lots(parsed):
    out, truth = parsed
    assert len(out.items) == out.report.rows - out.report.quarantined - truth["repeated_sku_rows"]
    merged = [i for i in out.items.values() if len(i.rows) == 2]
    assert len(merged) == 1 and len(merged[0].lots) >= 1


def test_services_are_kept_but_flagged(parsed):
    out, _ = parsed
    services = [i for i in out.items.values() if i.kind == "service"]
    assert len(services) == 3


def test_quality_flags_are_reported_but_rows_still_load(parsed):
    out, _ = parsed
    codes = {r["code"] for r in out.report.reviews}
    assert {"reserved_above_total", "negative_stock", "zero_cost", "cost_above_price"} <= codes
    assert all(r["source"] == "loader" for r in out.report.reviews)


def test_non_eur_currency_is_quarantined(parsed):
    out, _ = parsed
    assert out.report.quarantined == 1
    assert "currency_not_eur" in {r["code"] for r in out.report.reviews}


def test_inactive_status_is_kept(parsed):
    out, _ = parsed
    assert any(i.status == "inactive" for i in out.items.values())


def test_tax_interpretation_counts_rows(parsed):
    out, _ = parsed
    it = out.report.interpretations
    assert it["tax_included_rows"] + it["tax_excluded_rows"] == out.ok_rows
    assert it["tax_included_rows"] > 0 and it["timezone"] == "Europe/Madrid"


def test_gross_price_uses_the_tax_flag():
    out = parse_inventory(csv_bytes([row(SKU="A", **{"Precio Venta (€)": "10.00", "Impuesto Incluido": "No", "Tasa Impuesto (%)": "21"}),
                                     row(SKU="B", **{"Precio Venta (€)": "10.00", "Impuesto Incluido": "Sí", "Tasa Impuesto (%)": "21"})]), "i.csv", LIMITS)
    assert out.items["a"].pvp_gross == Decimal("12.10") and out.items["b"].pvp_gross == Decimal("10.00")
    assert out.items["a"].tax_included is False and out.items["b"].tax_included is True


def test_spanish_decimals_and_thousands():
    out = parse_inventory(csv_bytes([row(SKU="A", **{"Precio Venta (€)": "1.234,56", "Precio Coste (€)": "0,5"})]), "i.csv", LIMITS)
    assert out.items["a"].price == Decimal("1234.56") and out.items["a"].cost == Decimal("0.50")
    assert isinstance(out.items["a"].price, Decimal)


def test_invalid_numbers_are_quarantined_with_a_code():
    out = parse_inventory(csv_bytes([row(SKU="A", **{"Precio Venta (€)": "abc"}), row(SKU="B", **{"Stock Total": "x"}),
                                     row(SKU="C", **{"Precio Coste (€)": "-1"})]), "i.csv", LIMITS)
    assert out.report.quarantined == 3 and out.ok_rows == 0
    assert {r["code"] for r in out.report.reviews} >= {"invalid_number", "negative_amount"}


def test_blank_sku_is_quarantined():
    out = parse_inventory(csv_bytes([row(SKU="  ")]), "i.csv", LIMITS)
    assert out.report.quarantined == 1 and out.report.reviews[0]["code"] == "missing_sku"


def test_sku_matching_ignores_case_and_spaces_but_keeps_the_first_spelling():
    out = parse_inventory(csv_bytes([row(SKU="Syn-Ab"), row(SKU=" syn-ab ", Lote="L2")]), "i.csv", LIMITS)
    assert list(out.items) == ["syn-ab"] and out.items["syn-ab"].sku == "Syn-Ab" and len(out.items["syn-ab"].rows) == 2


def test_empty_supplier_column_is_accepted_and_names_are_kept_for_linking():
    out = parse_inventory(csv_bytes([row(SKU="A"), row(SKU="B", Proveedor="Proveedor X")]), "i.csv", LIMITS)
    assert out.items["a"].supplier_name == "" and out.items["b"].supplier_name == "Proveedor X"


def test_description_is_never_stored():
    out = parse_inventory(csv_bytes([row(SKU="A", **{"Descripción": "texto libre privado"})]), "i.csv", LIMITS)
    assert "texto libre privado" not in repr(out.items["a"])


def test_wrong_headers_are_rejected_with_the_missing_columns():
    with pytest.raises(LoaderFileError) as exc:
        parse_inventory(b"SKU,Nombre\nA,B\n", "i.csv", LIMITS)
    assert exc.value.code == "local_load_signature_mismatch" and "Lote" in exc.value.missing


def test_windows_1252_and_semicolon_files_are_read():
    text = ";".join(formats.INVENTORY_HEADERS) + "\n" + ";".join(row(SKU="A", Nombre="Niño")) + "\n"
    out = parse_inventory(text.encode("cp1252"), "i.csv", LIMITS)
    assert out.items["a"].name == "Niño"


def test_a_sku_longer_than_the_platform_keeps_is_quarantined():
    out = parse_inventory(csv_bytes([row(SKU="X" * 61), row(SKU="Y" * 60)]), "i.csv", LIMITS)
    assert out.report.quarantined == 1 and out.ok_rows == 1 and out.report.reviews[0]["code"] == "sku_too_long"
