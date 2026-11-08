"""MMI 004 contracts: supplier, supplier_link, load_result and conditions_block (synthetic example payloads only)."""

import json
import uuid
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["supplier", "supplier_link", "load_result", "conditions_block"]


def _registry() -> Registry:
    reg = Registry()
    for p in (ROOT / "dto").glob("*.schema.json"):
        reg = reg.with_resource(f"mmi/dto/{p.name}", Resource.from_contents(json.loads(p.read_text())))
    return reg


REG = _registry()


def errors(name: str, doc: dict) -> list:
    schema = json.loads((ROOT / "dto" / f"{name}.v1.schema.json").read_text())
    return list(jsonschema.Draft202012Validator(schema, registry=REG).iter_errors(doc))


U = str(uuid.uuid4())
M = {"amount": "12.50", "currency": "EUR"}

VALID = {
    "supplier": {"id": U, "name": "Proveedor Sintetico 01", "status": "active", "classification": "purchasing", "origin": "platform",
                 "erp_link_state": "none", "fiscal_type": "national", "country": "ES", "currency": "EUR", "has_note": False, "version": 1,
                 "payment_terms_days": 30, "order_channel": "email", "external_contact_id": None},
    "supplier_link": {"sku": "SYN-000001", "supplier_id": U, "cost": M, "cost_source": "inventory_export", "includes_recargo": False,
                      "pack_size": 6, "min_qty": 6, "supplier_reference": "REF-1", "rank": 1},
    "load_result": {"run_id": U, "kind": "inventory", "file_sha256": "a" * 64, "rows": 10, "loaded": 6, "updated": 1, "unchanged": 1,
                    "quarantined": 1, "excluded": 0, "services": 1, "differences": 0, "review": [{"row": 3, "code": "unmapped_reason", "detail": "x"}],
                    "interpretations": {"tax_included_rows": 2, "tax_excluded_rows": 8, "timezone": "Europe/Madrid"}},
    "conditions_block": {"v": 1, "lead_time_days": 3, "min_order_value": "150.00", "min_qty": None, "free_delivery_threshold": "300.00",
                         "delivery_charge": "5.00", "order_days": [1, 3], "currency": "EUR", "updated": "2026-11-08T10:00:00Z", "hash": "b" * 64},
}

INVALID = [
    ("supplier", {**VALID["supplier"], "status": "deleted"}),
    ("supplier", {**VALID["supplier"], "cif": "X1234567Z"}),          # tax id is never part of the contract
    ("supplier", {**VALID["supplier"], "notes": "free text"}),        # notes are never stored
    ("supplier", {**VALID["supplier"], "currency": "euro"}),
    ("supplier_link", {**VALID["supplier_link"], "cost_source": "guess"}),
    ("supplier_link", {k: v for k, v in VALID["supplier_link"].items() if k != "sku"}),
    ("load_result", {**VALID["load_result"], "kind": "tickets"}),
    ("load_result", {**VALID["load_result"], "loaded": -1}),
    ("conditions_block", {**VALID["conditions_block"], "order_days": [0, 8]}),
    ("conditions_block", {**VALID["conditions_block"], "min_order_value": 150.0}),   # money is a decimal string, never a float
]


@pytest.mark.parametrize("name", NAMES)
def test_valid_example_passes(name):
    assert errors(name, VALID[name]) == []


@pytest.mark.parametrize(("name", "doc"), INVALID, ids=[f"{n}-{i}" for i, (n, _) in enumerate(INVALID)])
def test_invalid_example_is_refused(name, doc):
    assert errors(name, doc)


def test_supplier_contract_has_no_sensitive_properties():
    props = json.loads((ROOT / "dto" / "supplier.v1.schema.json").read_text())["properties"]
    assert not {"cif", "tax_id", "iban", "swift", "bank", "notes", "note", "billing_address"} & set(props)
