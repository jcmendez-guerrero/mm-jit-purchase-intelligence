"""T012: MMI 002 contracts - example payloads validate, invalid ones are refused, and forecast.completed stays additive.

Synthetic values only. Money is a decimal string; weekdays are ISO 1..7; every DTO is closed (no extra properties).
"""

import json
import uuid
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
NEW_DTOS = [
    "supplier_terms", "product_supplier_terms", "policy_set", "budget_cap", "stocking_setting", "policy_override_request",
    "demand_rule", "lot_acquisition_cost", "seed_dataset", "seed_mapping", "seed_validation_result", "forecast_parameter",
    "forecast_accuracy", "scenario", "scenario_result", "scenario_sensitivity", "dashboard_summary",
]
NEW_EVENTS = [
    "forecast.seed.activated", "procurement.terms.changed", "procurement.scenario.ready", "inventory.rules.changed",
    "procurement.lot_cost.changed",
]


def _registry() -> Registry:
    reg = Registry()
    for sub in ("dto", "events"):
        for p in (ROOT / sub).glob("*.schema.json"):
            reg = reg.with_resource(f"mmi/{sub}/{p.name}", Resource.from_contents(json.loads(p.read_text())))
    return reg


REG = _registry()


def validator(sub: str, name: str, defs_payload: bool = False) -> jsonschema.Draft202012Validator:
    schema = json.loads((ROOT / sub / f"{name}.v1.schema.json").read_text())
    if defs_payload:
        schema = {"$schema": schema["$schema"], "$ref": "#/$defs/payload", "$defs": schema["$defs"]}
    return jsonschema.Draft202012Validator(schema, registry=REG)


def errors(sub, name, doc, **kw):
    return list(validator(sub, name, **kw).iter_errors(doc))


M = {"amount": "10.50", "currency": "EUR"}
U = str(uuid.uuid4())

VALID = {
    "supplier_terms": {"supplier_id": "supplier-a", "version": 1, "valid_from": "2026-01-01", "source": "manual", "revision": 1,
                       "lead_time_days": 3, "order_days": [1, 4], "delivery_weekdays": [2, 5], "min_order_value": M,
                       "discounts": [{"kind": "percent", "basis": "order_value", "threshold": "300.00", "value": "3"}],
                       "preferred": True, "disabled": False, "reliability": 90},
    "product_supplier_terms": {"variant_id": 9001, "supplier_id": "supplier-a", "version": 1, "valid_from": "2026-01-01",
                               "source": "manual", "revision": 1, "pack_multiple": 6, "lead_time_days": 5},
    "policy_set": {"scope": "segment", "key": "A-X", "valid_from": "2026-01-01", "revision": 1, "service_level": 0.97,
                   "safety_stock_units": 2, "min_units": 1, "max_units": 8},
    "budget_cap": {"period": "week", "scope": "global", "amount": M, "valid_from": "2026-01-01", "revision": 1},
    "stocking_setting": {"variant_id": 9002, "stocking_mode": "always_stocked", "min_floor_units": 1, "revision": 1},
    "policy_override_request": {"variant_id": 9002, "field": "safety_stock", "recommended_value": 0, "requested_value": 1,
                                "reason": "Producto de venta mensual que debe estar en tienda", "status": "pending"},
    "demand_rule": {"kind": "exclusion", "variant_id": 9001, "from_day": "2026-03-01", "to_day": "2026-03-05", "revision": 1,
                    "reason": "Promoción puntual"},
    "lot_acquisition_cost": {"variant_id": 9001, "supplier_id": "supplier-a", "lot": "L-01", "unit_cost": M, "quantity": 12,
                             "source": "confirmed_order"},
    "seed_dataset": {"id": U, "version": 1, "status": "uploaded", "origin": "synthetic", "file_sha256": "a" * 64},
    "seed_mapping": {"name": "plantilla", "column_map": {"Fecha": "day", "Cantidad": "quantity"}},
    "seed_validation_result": {"dataset_id": U, "accepted": 3, "quarantined": 1, "rows": [{"row_no": 4, "reason_key": "import_unknown_variant"}]},
    "forecast_parameter": {"scope": "global", "key": "horizon_days", "value": 28, "valid_from": "2026-01-01", "revision": 1},
    "forecast_accuracy": {"run_id": U, "segment": "A-X", "metric": "wape", "value": "0.23"},
    "scenario": {"name": "Sin proveedor B", "parameters": {"disabled_supplier_ids": ["supplier-b"], "budget": M}, "status": "computing"},
    "scenario_result": {"scenario_id": U, "supplier_id": "supplier-a", "order_total": M,
                        "lines": [{"variant_id": 9001, "quantity": 6, "unit_cost": M}],
                        "binding_constraints": [{"key": "min_order_value"}]},
    "scenario_sensitivity": {"scenario_id": U, "constraint_key": "min_order_value", "delta": "+10%", "cost_impact": M},
    "dashboard_summary": {"refreshed_at": "2026-11-05T10:00:00Z", "cards": [
        {"key": "inventory_value", "value": "1234.50", "unit": "EUR", "basis": "lot_acquisition_cost", "estimated_count": 2, "state": "ok"}]},
}

INVALID = [
    ("supplier_terms", {"order_days": [0, 8]}),
    ("supplier_terms", {"order_days": [1, 1]}),
    ("supplier_terms", {"min_order_value": {"amount": 10.5, "currency": "EUR"}}),
    ("supplier_terms", {"source": "guess"}),
    ("supplier_terms", {"unexpected": True}),
    ("supplier_terms", {"revision": 0}),
    ("policy_set", {"service_level": 1.5}),
    ("policy_set", {"safety_stock_units": -1}),
    ("budget_cap", {"amount": {"amount": "x", "currency": "EUR"}}),
    ("stocking_setting", {"stocking_mode": "sometimes"}),
    ("policy_override_request", {"reason": ""}),
    ("policy_override_request", {"status": "auto_approved"}),
    ("lot_acquisition_cost", {"source": "erp_movement_price"}),
    ("seed_dataset", {"origin": "mixed"}),
    ("seed_dataset", {"file_sha256": "short"}),
    ("seed_mapping", {"column_map": {"Notas": "notes"}}),
    ("forecast_accuracy", {"metric": "mape"}),
    ("scenario", {"status": "done"}),
    ("dashboard_summary", {"cards": [{"key": "pvp_total", "value": "1", "basis": "x"}]}),
]


@pytest.mark.parametrize("name", NEW_DTOS)
def test_new_dtos_exist_and_are_closed(name):
    schema = json.loads((ROOT / "dto" / f"{name}.v1.schema.json").read_text())
    assert schema["additionalProperties"] is False
    assert schema["$id"] == f"mmi/dto/{name}.v1"


@pytest.mark.parametrize("name", NEW_DTOS)
def test_valid_example_validates(name):
    assert errors("dto", name, VALID[name]) == []


@pytest.mark.parametrize(("name", "patch"), INVALID, ids=[f"{n}-{next(iter(p))}" for n, p in INVALID])
def test_invalid_example_is_refused(name, patch):
    doc = {**VALID[name], **patch}
    assert errors("dto", name, doc), f"{name} accepted {patch}"


@pytest.mark.parametrize("name", NEW_DTOS)
def test_required_properties_are_enforced(name):
    schema = json.loads((ROOT / "dto" / f"{name}.v1.schema.json").read_text())
    for req in schema["required"]:
        doc = {k: v for k, v in VALID[name].items() if k != req}
        assert errors("dto", name, doc), f"{name} accepted a document without {req}"


def test_no_dto_carries_free_text_notes_or_tax_ids():
    for name in NEW_DTOS:
        props = json.loads((ROOT / "dto" / f"{name}.v1.schema.json").read_text())["properties"]
        assert not {"notes", "note", "supplier_cif", "cif"} & set(props), name


def test_money_is_never_a_number():
    doc = {**VALID["lot_acquisition_cost"], "unit_cost": {"amount": 12.5, "currency": "EUR"}}
    assert errors("dto", "lot_acquisition_cost", doc)


EVENT_PAYLOADS = {
    "forecast.seed.activated": {"dataset_id": U, "version": 2, "action": "rolled_back"},
    "procurement.terms.changed": {"scope": "supplier_terms", "key": "supplier-a", "version": 3},
    "procurement.scenario.ready": {"scenario_id": U, "status": "ready"},
    "inventory.rules.changed": {"kind": "exclusion", "variant_id": 9001},
    "procurement.lot_cost.changed": {"variant_id": 9001, "supplier_id": "supplier-a", "lot": "L-01"},
}


@pytest.mark.parametrize("etype", NEW_EVENTS)
def test_new_event_payloads(etype):
    schema = json.loads((ROOT / "events" / f"{etype}.v1.schema.json").read_text())
    assert schema["allOf"][1]["properties"]["type"]["const"] == f"{etype}.v1"
    assert errors("events", etype, EVENT_PAYLOADS[etype], defs_payload=True) == []
    assert errors("events", etype, {**EVENT_PAYLOADS[etype], "values": [1]}, defs_payload=True)  # references only, no extra data
    bad = {k: v for k, v in EVENT_PAYLOADS[etype].items() if k != next(iter(EVENT_PAYLOADS[etype]))}
    assert errors("events", etype, bad, defs_payload=True)


def test_forecast_completed_stays_additive():
    old = {"run_id": U, "input_hash": "abc", "eligible_count": 10}
    assert errors("events", "forecast.completed", old, defs_payload=True) == []
    new = {**old, "dataset_version_id": U, "parameter_version_ids": [U]}
    assert errors("events", "forecast.completed", new, defs_payload=True) == []
    assert errors("events", "forecast.completed", {**old, "dataset_version_id": None}, defs_payload=True) == []
    assert errors("events", "forecast.completed", {**old, "dataset_version_id": "not-a-uuid"}, defs_payload=True) == []  # format is advisory
    assert errors("events", "forecast.completed", {**old, "parameter_version_ids": "x"}, defs_payload=True)
