"""T014: the forecast service's Spanish catalogue covers the import template and matches the synthetic fixtures."""

import seed_fixtures as sf
from i18n import catalogue, t

CANONICAL = ["variant_id", "sku", "day", "quantity", "warehouse", "kind", "provenance", "origin"]


def test_template_headers_cover_every_canonical_field():
    for f in CANONICAL:
        assert t(f"template.col.{f}")


def test_fixture_header_row_matches_the_template():
    expected = [t(f"template.col.{f}") for f in ("variant_id", "day", "quantity", "warehouse", "kind", "provenance", "origin")]
    assert sf.HEADER == expected


def test_kind_and_origin_labels_match_fixtures():
    text = sf.static("valid.csv").decode("utf-8")
    for label in (t("kind.estimated"), t("kind.manual_forecast"), t("kind.observed_external"), t("origin.synthetic")):
        assert label in text


def test_every_message_is_spanish_text_not_a_key():
    assert all(v and v != k for k, v in catalogue().items())
