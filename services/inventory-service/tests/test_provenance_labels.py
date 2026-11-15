"""T014: no value from seed, local-export, imputed or unknown sources is ever labelled observed (SC-002, FR-014)."""

import pytest
from demand.provenance import ESTIMATED, LABELS, MANUAL, OBSERVED, SURROGATE_BASE, provenance


def test_erp_rows_with_a_real_id_are_observed():
    assert provenance("erp_sync", 123) == OBSERVED
    assert provenance("erp", 1) == OBSERVED


@pytest.mark.parametrize("origin", ["seed", "local_export", "imputed", "synthetic", "", "ERP", "unknown", None])
def test_every_other_origin_is_never_observed(origin):
    assert provenance(origin, 123) == ESTIMATED


def test_manual_stays_manual():
    assert provenance("manual", 123) == MANUAL


@pytest.mark.parametrize("variant_id", [SURROGATE_BASE, SURROGATE_BASE + 41])
def test_local_export_ids_are_never_observed_even_if_the_origin_says_erp(variant_id):
    assert provenance("erp_sync", variant_id) == ESTIMATED


def test_just_below_the_reserved_range_is_still_a_real_id():
    assert provenance("erp_sync", SURROGATE_BASE - 1) == OBSERVED


def test_labels_are_the_three_allowed_values():
    assert set(LABELS) == {"observed", "estimated", "manual"}


def test_the_series_export_labels_every_variant(client, engine):
    from classification.run import compute_segments
    from test_api import auth
    from test_classification import SMOOTH, seed_variant

    seed_variant(engine, 1, 1, SMOOTH, price="20")
    with engine.begin() as c:
        compute_segments(c)
    series = client.get("/export/series", headers=auth()).json()["series"]
    assert series and all(s["provenance"] == OBSERVED for s in series)
