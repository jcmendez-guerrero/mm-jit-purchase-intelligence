"""T003/T004: the synthetic seed and terms fixtures exist, are made up, and the hostile ones really are hostile."""

import io
import json
import zipfile
from pathlib import Path

import seed_fixtures as sf

TERMS = Path(__file__).resolve().parents[1] / "fixtures" / "terms" / "terms.json"


def test_static_csvs_use_only_synthetic_ids():
    for name in ("valid.csv", "partly_invalid.csv", "mixed_origin.csv"):
        text = sf.static(name).decode("utf-8")
        assert text.splitlines()[0].split(";") == sf.HEADER
        for line in text.splitlines()[1:]:
            sku = line.split(";")[0]
            assert sku.startswith("EJ-") and 9001 <= int(sku[3:]) <= 9999            # fictional SKUs only


def test_partly_invalid_covers_each_failure_kind():
    text = sf.static("partly_invalid.csv").decode("utf-8")
    assert "9999" in text and ";-3;" in text and "1999-01-01" in text and "2026-02-30" in text and ";abc;" in text
    lines = text.splitlines()[1:]
    assert len(lines) != len(set(lines))  # duplicates present


def test_mixed_origin_has_both_origins():
    text = sf.static("mixed_origin.csv").decode("utf-8")
    assert "sintético" in text and ";real" in text


def test_valid_xlsx_is_a_zip_package_and_wrong_signature_is_not():
    assert sf.valid_xlsx().startswith(sf.XLSX_MAGIC)
    assert not sf.wrong_signature_xlsx().startswith(sf.XLSX_MAGIC)


def test_macro_workbook_carries_a_macro_part():
    names = zipfile.ZipFile(io.BytesIO(sf.macro_workbook())).namelist()
    assert "xl/vbaProject.bin" in names


def test_formula_files_hold_formula_prefixes():
    sheet = zipfile.ZipFile(io.BytesIO(sf.formula_xlsx())).read("xl/worksheets/sheet1.xml")
    assert b"<f>1+1</f>" in sheet and b"HYPERLINK" in sheet  # stored as formula elements, which a parser must not evaluate
    csv = sf.formula_csv().decode("utf-8")
    assert all(p in csv for p in (";=cmd", ";+SUM", ";@SUM"))


def test_oversized_and_bomb_exceed_their_limits():
    assert len(sf.oversized_csv(1024 * 1024)) > 1024 * 1024
    bomb = sf.decompression_bomb_xlsx(8)
    assert len(bomb) < 100 * 1024
    assert sum(i.file_size for i in zipfile.ZipFile(io.BytesIO(bomb)).infolist()) >= 8 * 1024 * 1024


def test_terms_fixture_is_synthetic_and_has_each_invalid_case():
    data = json.loads(TERMS.read_text(encoding="utf-8"))
    assert all(s["name"].startswith("Proveedor Sintético") for s in data["suppliers"])
    assert set(data["invalid"]) == {"overlapping_windows", "threshold_below_minimum", "negative_amount", "invalid_weekday"}
    assert data["expired"]["valid_to"] < "2026-01-01" and data["future"]["valid_from"] > "2026-12-31"
