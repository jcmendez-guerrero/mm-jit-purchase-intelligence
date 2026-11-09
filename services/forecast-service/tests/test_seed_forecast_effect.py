"""MMI-7 T050 + T031: seeds rescue only variants whose sole ineligibility is "new" (dense enough, long enough once combined); uncovered variants are
unchanged; rollback returns the series to what it was just before the activation. Synthetic data only."""

from datetime import date, timedelta

from conftest import KNOWN, export_series
from runs.seeds import apply_seeds, load_active
from seeds.lifecycle import activate, register_upload, rollback, validate_dataset
from upload_settings import ParseLimits

L = ParseLimits()
SKUS = {f"EJ-{v}": v for v in KNOWN}
MIN_HISTORY = 56
HEADER = "SKU;Fecha;Cantidad;Tipo de dato;Origen;Sintético/Real"


def csv(rows):
    return (HEADER + "\n" + "\n".join(f"{sku};{day.isoformat()};{qty};estimado;Hoja sintética A;sintético" for sku, day, qty in rows) + "\n").encode()


def dense(sku, qty, days=40, every=1, end=date(2025, 12, 31)):
    return [(sku, end - timedelta(days=i), qty) for i in range(0, days, every)]


def series():
    """9001 new (20 days); 9002 enough history (60 days); 9003 new; 9004 ineligible for another reason; 9005 has no seed rows."""
    return [
        export_series(9001, [1] * 20, "new", False, ["new"]),
        export_series(9002, [1] * 60, "smooth", True),
        export_series(9003, [1] * 20, "new", False, ["new"]),
        export_series(9004, [1] * 20, "new", False, ["new", "data_quality"]),
        export_series(9005, [1] * 20, "new", False, ["new"]),
    ]


def seed_file(qty=2):
    rows = dense("EJ-9001", qty) + dense("EJ-9002", qty) + dense("EJ-9003", qty, days=40, every=5) + dense("EJ-9004", qty)
    return csv(rows)


def activate_file(conn, store, data, who="approver-9"):
    up = register_upload(conn, store, "datos.csv", data, "Hoja", "buyer-1", L)
    validate_dataset(conn, store, up["id"], up["suggested_mapping"], KNOWN, "buyer-2", L, sku_map=SKUS)
    activate(conn, store, up["id"], who)
    return up["id"]


def test_only_new_variants_with_dense_enough_seeds_are_rescued_and_the_rest_is_unchanged(conn, store):
    before = series()
    activate_file(conn, store, seed_file())
    out, report = apply_seeds(before, load_active(conn), MIN_HISTORY)
    by_id = {s["variant_id"]: s for s in out}
    assert report.used == {9001} and report.skipped_sparse == {9003}
    assert by_id[9001]["segment"]["forecast_eligible"] is True and len(by_id[9001]["demand"]) == 40 + 20
    assert by_id[9002] == before[1]                                  # enough actual history: seeds are not consulted
    assert by_id[9003] == before[2]                                  # too sparse (1 day in 5)
    assert by_id[9004] == before[3]                                  # ineligible for a reason a longer history cannot cure
    assert by_id[9005] == before[4]                                  # not covered by the dataset


def test_a_seed_that_leaves_the_combined_history_below_the_minimum_does_not_rescue(conn, store):
    before = series()
    activate_file(conn, store, csv(dense("EJ-9001", 2, days=20)))     # 20 seed days + 20 actual days = 40 < 56
    out, report = apply_seeds(before, load_active(conn), MIN_HISTORY)
    assert not report.used and out[0]["segment"]["forecast_eligible"] is False


def test_rollback_returns_the_series_to_what_it_was_before_the_activation(conn, store):
    before = series()
    assert load_active(conn) is None                                  # no dataset: nothing is consulted
    activate_file(conn, store, seed_file())
    changed, _ = apply_seeds(before, load_active(conn), MIN_HISTORY)
    assert changed != before
    rollback(conn, store, "approver-9", reason_code="wrong_figures")
    assert load_active(conn) is None                                  # nothing active again, so the forecast input is the original series
    assert before == series()                                         # and the inputs were never modified


def test_rolling_back_the_second_dataset_restores_the_first_ones_series(conn, store):
    before = series()
    activate_file(conn, store, seed_file(qty=2))
    first, _ = apply_seeds(before, load_active(conn), MIN_HISTORY)
    activate_file(conn, store, seed_file(qty=5))
    second, _ = apply_seeds(before, load_active(conn), MIN_HISTORY)
    assert second != first                                            # the newer dataset changes the rescued history
    rollback(conn, store, "approver-9", reason_code="wrong_figures")
    restored, _ = apply_seeds(before, load_active(conn), MIN_HISTORY)
    assert restored == first
