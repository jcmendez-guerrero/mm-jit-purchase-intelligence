"""T016: load report: balanced counts, no personal data in review details, shape of the load_result contract."""

import json
from pathlib import Path

import jsonschema
import pytest
from export_loader.report import LoadReport, UnbalancedReport

SCHEMA = json.loads((Path(__file__).resolve().parents[4] / "packages/contracts/dto/load_result.v1.schema.json").read_text())


def make(rows=10) -> LoadReport:
    return LoadReport(kind="inventory", file_sha256="a" * 64, rows=rows)


def test_balanced_report_passes_and_matches_the_contract():
    r = make(10)
    r.loaded, r.updated, r.unchanged, r.services = 5, 1, 1, 1
    r.review(3, "unmapped_reason", "Motivo no reconocido")
    r.exclude(1)
    r.quarantined = 1
    result = r.result()
    jsonschema.validate(result, SCHEMA)
    assert result["loaded"] + result["updated"] + result["unchanged"] + result["quarantined"] + result["excluded"] + result["services"] == 10


def test_unbalanced_report_raises():
    r = make(10)
    r.loaded = 3
    with pytest.raises(UnbalancedReport):
        r.result()


def test_review_detail_never_keeps_emails_or_long_numbers():
    r = make()
    r.review(2, "bad_value", "contact a.b@example.org iban ES9121000418450200051332 tel 600123456")
    detail = r.reviews[0]["detail"]
    assert "@" not in detail and "ES9121000418450200051332" not in detail and "600123456" not in detail


def test_review_detail_is_capped():
    r = make()
    r.review(2, "bad_value", "x" * 500)
    assert len(r.reviews[0]["detail"]) <= 200


def test_review_code_must_be_snake_case():
    r = make()
    with pytest.raises(ValueError):
        r.review(2, "Bad Code", "x")


def test_review_source_defaults_to_loader():
    r = make()
    r.review(2, "unknown_sku")
    assert r.reviews[0]["source"] == "loader"
