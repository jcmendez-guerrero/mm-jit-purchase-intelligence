"""MMI-7 T011: the template asks for the SKU and never for the ERP variant id; the mapping recognises the SKU headers."""

from seeds import mapping as mp
from seeds.template import COLUMNS, template_csv, template_xlsx


def test_the_template_has_a_sku_column_and_no_internal_id_in_either_format():
    assert COLUMNS[0] == "sku" and "variant_id" not in COLUMNS
    text = template_csv().decode("utf-8-sig")
    assert text.splitlines()[0].startswith("SKU;") and "variante" not in text.lower() and "variant" not in text.lower()
    from io import BytesIO

    from openpyxl import load_workbook

    ws = load_workbook(BytesIO(template_xlsx())).active
    assert ws["A1"].value == "SKU" and all("variante" not in str(c.value).lower() for row in ws.iter_rows() for c in row)


def test_the_example_rows_use_fictional_skus():
    rows = template_csv().decode("utf-8-sig").splitlines()[1:]
    assert rows and all(r.split(";")[0].startswith("EJ-") for r in rows)


def test_the_mapping_recognises_the_sku_headers_and_requires_a_product_column():
    assert mp.suggest(["SKU", "Fecha", "Cantidad"]) == {"SKU": "sku", "Fecha": "day", "Cantidad": "quantity"}
    assert mp.suggest(["Referencia"]) == {"Referencia": "sku"}
    assert mp.missing_required({"Fecha": "day", "Cantidad": "quantity", "Tipo": "kind", "Origen": "provenance", "Sint": "origin"})[0] == "sku"
    assert "sku" not in mp.missing_required({"S": "sku", "Fecha": "day", "Cantidad": "quantity", "Tipo": "kind", "Origen": "provenance", "Sint": "origin"})
