"""MMI-7 T010 + T055: seed rows are matched by SKU; ERP export files are refused. Synthetic data only."""

from datetime import date

import pytest
import seed_fixtures as sf
from conftest import KNOWN, export_series
from seeds.export_shapes import erp_export_shape
from seeds.lifecycle import register_upload, validate_dataset
from seeds.storage import SeedFileError
from seeds.validation import validate_rows
from sqlalchemy import select
from upload_settings import ParseLimits

L = ParseLimits()
TODAY = date(2026, 11, 9)
SKUS = {"EJ-0001": 9001, "EJ-0002": 9002, "ej-0003": 9003, "EJ-0003": 9004}      # the last two differ only by case: ambiguous


def row(**kw):
    base = {"sku": "EJ-0001", "day": "2026-01-05", "quantity": "2", "warehouse": "", "kind": "estimado", "provenance": "Hoja sintética A", "origin": "sintético"}
    return {**base, **kw}


def test_a_known_sku_is_accepted_and_resolved_to_its_variant():
    v = validate_rows([row(), row(sku=" ej-0002 ", day="2026-01-06")], KNOWN, TODAY, sku_map=SKUS)
    assert [(a.sku, a.variant_id) for a in v.accepted] == [("EJ-0001", 9001), ("ej-0002", 9002)] and not v.quarantined


def test_unknown_and_ambiguous_skus_are_quarantined_not_guessed():
    v = validate_rows([row(sku="NO-EXISTE"), row(sku="EJ-0003", day="2026-01-06")], KNOWN, TODAY, sku_map=SKUS)
    assert [q.reason_key for q in v.quarantined] == ["import_unknown_sku", "import_ambiguous_sku"] and not v.accepted and v.total == 2


def test_a_row_with_only_a_variant_id_is_rejected_with_sku_required():
    v = validate_rows([row(sku="", variant_id="9001")], KNOWN, TODAY, sku_map=SKUS)
    assert [q.reason_key for q in v.quarantined] == ["import_sku_required"] and not v.accepted


def test_the_variant_id_column_is_never_trusted_when_a_sku_is_given():
    v = validate_rows([row(variant_id="9002")], KNOWN, TODAY, sku_map=SKUS)
    assert [a.variant_id for a in v.accepted] == [9001]


def test_duplicates_are_detected_per_sku_and_day():
    v = validate_rows([row(), row()], KNOWN, TODAY, sku_map=SKUS)
    assert [q.reason_key for q in v.quarantined] == ["import_duplicate_row"] and len(v.accepted) == 1


@pytest.mark.parametrize("headers,shape", [
    (["SKU", "Nombre", "Stock Disponible", "Stock Total", "Estado"], "inventory"),
    (["Fecha", "Producto", "SKU", "Tipo", "Motivo", "Caducidad", "Cantidad"], "movements"),
    (["ID", "Nombre Empresa", "CIF", "IBAN"], "suppliers"),
    (["SKU", "Fecha", "Cantidad", "Tipo de dato", "Origen", "Sintético/Real"], None),
    (["Referencia", "Fecha", "Cantidad", "Almacén"], None),
])
def test_erp_export_layouts_are_recognised_and_the_seed_template_is_not(headers, shape):
    assert erp_export_shape(headers) == shape


def test_an_erp_export_is_refused_before_any_dataset_is_created(conn, store):
    from db.tables import seed_datasets

    data = "SKU;Nombre;Stock Disponible;Stock Total\nSYN-1;Producto sintético;3;3\n".encode()
    with pytest.raises(SeedFileError) as e:
        register_upload(conn, store, "inventario.csv", data, "Hoja", "buyer-1", L)
    assert e.value.code == "import_erp_export_refused"
    assert conn.execute(select(seed_datasets.c.id)).first() is None


def test_a_sku_file_validates_end_to_end_with_the_sku_map(conn, store):
    data = "SKU;Fecha;Cantidad;Tipo de dato;Origen;Sintético/Real\nEJ-0001;2026-01-05;2;estimado;Hoja sintética A;sintético\nNO-EXISTE;2026-01-06;1;estimado;Hoja sintética A;sintético\n".encode()
    up = register_upload(conn, store, "datos.csv", data, "Hoja", "buyer-1", L)
    assert up["missing"] == []
    res = validate_dataset(conn, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-2", L, sku_map=SKUS)
    assert (res["accepted"], res["quarantined"]) == (1, 1)
    from db.tables import seed_datasets, seed_rows

    ds = conn.execute(select(seed_datasets).where(seed_datasets.c.id == up["id"])).one()
    assert ds.validated_by == "buyer-2" and conn.execute(select(seed_rows.c.sku, seed_rows.c.variant_id)).one() == ("EJ-0001", 9001)


def test_a_sku_workbook_goes_through_the_same_path_as_the_csv(conn, store):
    """MMI-7 T004: the SKU template in Excel format (made-up SKUs)."""
    up = register_upload(conn, store, "datos.xlsx", sf.valid_xlsx(), "Hoja", "buyer-1", L)
    assert up["format"] == "xlsx" and up["missing"] == [] and up["suggested_mapping"]["SKU"] == "sku"
    res = validate_dataset(conn, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-2", L, sku_map={f"EJ-{v}": v for v in KNOWN})
    assert (res["accepted"], res["quarantined"]) == (3, 0)


def test_two_products_with_exactly_the_same_sku_are_ambiguous_not_resolved_to_either():
    """MMI-7 T073 (FR-007): the ERP does not guarantee unique SKUs, so a shared SKU is never resolved by chance."""
    from seeds.lookup import lookups_from_series

    series = [export_series(9001, [1] * 20), export_series(9002, [1] * 20), export_series(9003, [1] * 20)]
    series[1]["sku"] = series[0]["sku"]                                                # variants 9001 and 9002 both carry EJ-9001
    known, skus = lookups_from_series(series)
    assert known == {9001, 9002, 9003} and skus == {"EJ-9001": {9001, 9002}, "EJ-9003": {9003}}
    v = validate_rows([row(sku="EJ-9001"), row(sku="EJ-9003", day="2026-01-06")], known, TODAY, sku_map=skus)
    assert [q.reason_key for q in v.quarantined] == ["import_ambiguous_sku"] and [a.variant_id for a in v.accepted] == [9003]


def test_products_without_a_sku_in_the_series_are_left_out_of_the_lookup():
    from seeds.lookup import lookups_from_series

    item = export_series(9001, [1] * 20)
    del item["sku"]
    assert lookups_from_series([item]) == ({9001}, {})
