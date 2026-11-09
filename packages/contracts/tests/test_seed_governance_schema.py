"""MMI-7 T056 + T072: the seed dataset contracts carry the governance fields as optional, additive properties; reasons are a pick-list code plus a short detail."""

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "dto" / "seed_dataset.v1.schema.json").read_text(encoding="utf-8"))
SUMMARY = json.loads((ROOT / "dto" / "seed_dataset_summary.v1.schema.json").read_text(encoding="utf-8"))
NEW = ("validated_by", "mapping_chosen_by", "rollback_reason_code", "rollback_reason_detail", "self_activation_reason_code", "self_activation_reason_detail")
ROLLBACK_CODES = ["wrong_figures", "wrong_file", "test", "replaced_by_newer", "other"]
SELF_ACTIVATION_CODES = ["only_person", "urgent", "other"]
BASE = {"id": "5ba24d0e-5860-4dc0-baf2-caf0cb702742", "version": 1, "status": "validated", "origin": "synthetic", "file_sha256": "a" * 64}


def codes(schema, field):
    return next(o["enum"] for o in schema["properties"][field]["oneOf"] if "enum" in o)


def test_the_governance_fields_are_declared_and_optional():
    assert all(f in SCHEMA["properties"] and f not in SCHEMA["required"] for f in NEW)
    assert "rollback_reason" not in SCHEMA["properties"] and "self_activated_reason" not in SCHEMA["properties"]      # no free-text reason any more (FR-033)


def test_the_reason_codes_are_the_fixed_lists_of_the_spec():
    for schema in (SCHEMA, SUMMARY):
        assert codes(schema, "rollback_reason_code") == ROLLBACK_CODES
        assert codes(schema, "self_activation_reason_code") == SELF_ACTIVATION_CODES


def test_a_dataset_with_and_without_them_validates_and_a_bad_reason_does_not():
    jsonschema.validate(BASE, SCHEMA)
    jsonschema.validate({**BASE, "validated_by": "buyer-2", "mapping_chosen_by": "buyer-2", "rollback_reason_code": "wrong_figures", "rollback_reason_detail": "Cifras erróneas",
                         "self_activation_reason_code": None, "self_activation_reason_detail": None}, SCHEMA)
    bad = [("rollback_reason_code", "because"), ("self_activation_reason_code", "wrong_figures"), ("rollback_reason_detail", "x" * 101), ("self_activation_reason_detail", "x" * 101)]
    for field, value in bad:
        try:
            jsonschema.validate({**BASE, field: value}, SCHEMA)
        except jsonschema.ValidationError:
            continue
        raise AssertionError(f"{field} accepted {value[:12]!r}")


def test_the_status_enum_keeps_the_deprecated_approved_value_so_the_change_stays_additive():
    assert "approved" in SCHEMA["properties"]["status"]["enum"]


def test_the_list_item_shows_the_chosen_reason_and_leaves_the_detail_optional():
    props = SUMMARY["properties"]
    assert {"rollback_reason_code", "self_activation_reason_code", "rollback_reason_detail", "self_activation_reason_detail"} <= set(props)
    assert not {"rollback_reason_detail", "self_activation_reason_detail"} & set(SUMMARY["required"])           # admins-only: absent for everyone else
