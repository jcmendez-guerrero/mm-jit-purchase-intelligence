"""T091: the loader keeps the rows the Siweb payload cannot express; what the platform can judge is passed through."""

from __future__ import annotations

import pytest
from export_loader.service import LoaderService
from generator.exports import write_exports


@pytest.fixture
def loaded(tmp_path):
    files = tmp_path / "files"
    data = write_exports(files, seed=42)
    pushes: list[dict] = []
    s = LoaderService(tmp_path / "state", pushes.append)
    inv = s.load("inventory", "inventario.csv", (files / "inventario.csv").read_bytes(), acknowledge_interpretation=True)
    mov = s.load("movements", "movimientos.xlsx", (files / "movimientos.xlsx").read_bytes())
    return s, pushes, inv, mov, data


def test_pass_through_cases_are_loaded_not_held_by_the_loader(loaded):
    s, pushes, _, _, data = loaded
    raw_expiry = [m for m in pushes[-1]["movements"] if m["expiry_date"] and "-" not in m["expiry_date"]]
    assert len(raw_expiry) == data.truth["bad_expiry_rows"]            # malformed expiry travels as raw text for the platform to quarantine
    codes = {r["code"] for r in s.review_items()}
    assert "malformed_expiry" not in codes and "ambiguous_timestamp" not in codes


def test_rows_the_payload_cannot_express_stay_in_the_loader_review(loaded):
    s, _, _, _, _ = loaded
    items = s.review_items()
    codes = {i["code"] for i in items if i["kind"] == "movements"}
    assert {"unknown_sku", "unmapped_reason", "sign_mismatch"} <= codes
    assert {i["code"] for i in items if i["kind"] == "inventory"} >= {"currency_not_eur", "zero_cost"}


def test_every_item_is_labelled_with_its_source_and_has_no_personal_data(loaded):
    s, _, _, _, _ = loaded
    for i in s.review_items():
        assert i["source"] == "loader" and i["row"] >= 2
        assert "@" not in i["detail"]


def test_the_review_follows_the_latest_load_of_each_kind(loaded, tmp_path):
    s, _, _, _mov, _ = loaded
    n = len([i for i in s.review_items() if i["kind"] == "movements"])
    files = tmp_path / "files"
    s.load("movements", "movimientos.xlsx", (files / "movimientos.xlsx").read_bytes())
    assert len([i for i in s.review_items() if i["kind"] == "movements"]) == n          # replaced, not accumulated


def test_the_quarantine_counts_match_the_review_items_that_quarantine(loaded):
    s, _, inv, mov, _ = loaded
    quarantining = {"missing_sku", "unknown_type", "currency_not_eur", "invalid_number", "negative_amount", "unknown_tax_flag", "invalid_date",
                    "unknown_sku", "unmapped_reason", "non_integer_quantity", "zero_quantity", "sign_mismatch"}
    for kind, res in (("inventory", inv), ("movements", mov)):
        assert len([i for i in s.review_items() if i["kind"] == kind and i["code"] in quarantining]) == res["quarantined"]
