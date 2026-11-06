"""T099: row validation - nothing is dropped silently."""

from datetime import date

import pytest
import seed_fixtures as sf
from conftest import KNOWN
from seeds import mapping as mp
from seeds.parsers import parse_csv
from seeds.storage import SeedFileError
from seeds.validation import parse_day, parse_quantity, validate_rows
from upload_settings import ParseLimits

TODAY = date(2026, 11, 9)


def row(**kw):
    base = {"variant_id": "9001", "day": "2026-01-05", "quantity": "2", "warehouse": "", "kind": "estimado", "provenance": "Hoja sintética A", "origin": "sintético"}
    return {**base, **kw}


def reasons(rows):
    return [q.reason_key for q in validate_rows(rows, KNOWN, TODAY).quarantined]


def test_a_clean_file_is_accepted_entirely():
    v = validate_rows([row(), row(variant_id="9002", day="2026-01-06", kind="previsión_manual")], KNOWN, TODAY)
    assert (len(v.accepted), len(v.quarantined), v.origin) == (2, 0, "synthetic") and {a.kind for a in v.accepted} == {"estimated", "manual_forecast"}


def test_each_bad_row_gets_a_stable_reason_and_the_counts_add_up():
    rows = [row(variant_id="9999"), row(variant_id="x"), row(quantity="-3"), row(quantity="abc"), row(day="31/02/2026"), row(day="2001-01-01"), row(day="2035-01-01"),
            row(kind="otra cosa"), row(provenance=" "), row(day="2026-01-05"), row(day="2026-01-05")]
    v = validate_rows(rows, KNOWN, TODAY)
    assert [q.reason_key for q in v.quarantined] == ["import_unknown_variant", "import_unknown_variant", "import_negative_quantity", "import_invalid_quantity", "import_invalid_date",
                                                     "import_date_out_of_range", "import_date_out_of_range", "import_unknown_kind", "import_missing_provenance", "import_duplicate_row"]
    assert len(v.accepted) == 1 and v.total == len(rows)


def test_the_repository_fixture_with_bad_rows_is_split_correctly():
    _, rows = parse_csv(sf.static("partly_invalid.csv"), ParseLimits())
    mapped = mp.apply(mp.suggest(list(rows[0])), rows)
    v = validate_rows(mapped, KNOWN, TODAY)
    assert [q.reason_key for q in v.quarantined] == ["import_unknown_variant", "import_negative_quantity", "import_negative_quantity", "import_date_out_of_range", "import_invalid_date",
                                                     "import_invalid_quantity", "import_missing_provenance", "import_duplicate_row"]
    assert len(v.accepted) == 2 and v.total == len(rows) == 10


def test_mixed_origin_refuses_the_whole_file():
    with pytest.raises(SeedFileError) as e:
        validate_rows([row(), row(variant_id="9002", origin="real")], KNOWN, TODAY)
    assert e.value.code == "import_mixed_origin"


def test_dates_in_both_formats_and_decimal_commas_and_thousands():
    assert parse_day("05/01/2026")[0] == date(2026, 1, 5) and parse_day("2026-01-05")[0] == date(2026, 1, 5)
    assert str(parse_quantity("1,5")) == "1.5" and str(parse_quantity("1.234,5")) == "1234.5" and str(parse_quantity("2")) == "2"
    for bad in ("1,2,3", "NaN", "inf", ""):
        with pytest.raises(Exception):  # noqa: B017 - any parse failure is quarantined by the caller
            parse_quantity(bad)


def test_a_dst_ambiguous_local_time_is_quarantined_and_other_times_are_not():
    assert reasons([row(day="2026-10-25 02:30")]) == ["import_ambiguous_time"]            # the autumn clock change repeats 02:00-03:00
    assert reasons([row(day="2026-10-25 04:30")]) == [] and reasons([row(day="2026-07-01 02:30")]) == []


def test_notes_and_tax_ids_never_reach_validation_because_the_mapping_drops_them():
    headers = ["ID de variante Siweb", "Fecha", "Cantidad", "Tipo de dato", "Origen", "Sintético/Real", "Notas", "CIF proveedor"]
    cm = mp.suggest(headers)
    assert "Notas" not in cm and "CIF proveedor" not in cm
    applied = mp.apply(cm, [dict.fromkeys(headers, "x") | {"ID de variante Siweb": "9001"}])
    assert set(applied[0]) <= set(mp.CANONICAL)


def test_the_mapping_suggests_spanish_headers_and_reports_missing_fields():
    cm = mp.suggest(["ID de variante Siweb", "Fecha", "Cantidad", "Almacén", "Tipo de dato", "Origen", "Sintético/Real"])
    assert set(cm.values()) == set(mp.CANONICAL) - {"sku"} and mp.missing_required(cm) == []
    assert mp.missing_required({"Fecha": "day"}) == ["variant_id", "quantity", "kind", "provenance", "origin"]
    with pytest.raises(mp.MappingError):
        mp.validate_map({"a": "day", "b": "day"})
    with pytest.raises(mp.MappingError):
        mp.validate_map({"a": "notes"})
