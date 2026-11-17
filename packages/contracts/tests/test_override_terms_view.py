"""MMI-16 (spec 016): override_terms_view is addressed by SKU and can never carry the Siweb variant id (synthetic payloads only)."""

import json
from pathlib import Path

import jsonschema

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "dto" / "override_terms_view.v1.schema.json").read_text())
EFFECTIVE = {"lead_time_days": 3, "pack_multiple": None, "min_qty_units": None, "payment_terms_days": 30, "preferred": False, "reliability": None,
             "disabled": False, "sources": {"lead_time_days": "override"}, "conflicts": [], "supplier_version": 1, "override_version": 1, "flags": []}
VIEW = {"sku": "SYN-0001", "supplier_id": "s1", "version": 1, "override": {"lead_time_days": 3}, "history": [], "effective": EFFECTIVE}


def errors(doc: dict) -> list:
    return list(jsonschema.Draft202012Validator(SCHEMA).iter_errors(doc))


def test_a_view_by_sku_is_valid():
    assert errors(VIEW) == []
    assert errors({**VIEW, "override": None, "version": 0}) == []


def test_a_variant_id_is_refused():
    assert errors({**VIEW, "variant_id": 9001}) != []


def test_the_sku_is_required_and_not_empty():
    assert errors({k: v for k, v in VIEW.items() if k != "sku"}) != []
    assert errors({**VIEW, "sku": ""}) != []
