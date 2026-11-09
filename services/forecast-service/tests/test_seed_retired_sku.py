"""MMI-7 T041 (edge case): seed rows for a product that left the catalogue stop contributing and are reported, in the dry run."""

from datetime import date, timedelta
from decimal import Decimal

from conftest import KNOWN, export_series
from runs.seeds import ActiveSeeds, apply_seeds
from seeds.dryrun import dry_run
from seeds.lifecycle import activate, register_upload, validate_dataset
from upload_settings import ParseLimits

L = ParseLimits()
SKUS = {f"EJ-{v}": v for v in KNOWN}
MIN = 56
HEADER = "SKU;Fecha;Cantidad;Tipo de dato;Origen;Sintético/Real"


def dense_days(days=40):
    end = date(2025, 12, 31)
    return [end - timedelta(days=i) for i in range(days)]


def test_seed_rows_for_a_variant_missing_from_the_series_do_not_contribute_and_are_reported():
    seeds = ActiveSeeds("ds", 1, {v: {d: Decimal(3) for d in dense_days()} for v in (9001, 9099)})
    out, rep = apply_seeds([export_series(9001, [1] * 20, "new", False, ["new"])], seeds, MIN)
    assert rep.used == {9001} and rep.retired == {9099} and len(out) == 1


def test_the_dry_run_lists_the_variants_that_left_the_catalogue(conn, store):
    rows = "\n".join(f"EJ-{v};{d.isoformat()};3;estimado;Hoja sintética A;sintético" for v in (9001, 9002) for d in dense_days())
    up = register_upload(conn, store, "datos.csv", (HEADER + "\n" + rows + "\n").encode(), "Hoja", "buyer-1", L)
    validate_dataset(conn, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-2", L, sku_map=SKUS)
    activate(conn, store, up["id"], "approver-9")
    only_9001 = [export_series(9001, [1] * 20, "new", False, ["new"])]            # 9002 was retired from the catalogue after the import
    result = dry_run(conn, up["id"], only_9001, MIN)
    assert result["retired_variants"] == [9002]
