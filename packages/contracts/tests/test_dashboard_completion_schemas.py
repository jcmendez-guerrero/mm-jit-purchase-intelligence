"""Feature 014 (T004): the additive dashboard contracts (SKU page, drill-down page with the new kinds, freshness) accept valid payloads and refuse invalid ones.

The v1 summary and v2 indicators schemas stay frozen: their hashes are pinned in the inventory service tests (test_dashboard_indicators_unchanged.py). Synthetic values only.
"""

import copy
import json
from pathlib import Path

import jsonschema
import pytest

DTO = Path(__file__).resolve().parents[1] / "dto"


def load(name: str) -> dict:
    return json.loads((DTO / f"{name}.v1.schema.json").read_text(encoding="utf-8"))


def validate(name: str, payload: object) -> None:
    jsonschema.validate(payload, load(name), cls=jsonschema.Draft202012Validator)


SKU = {
    "sku": "SYN-001", "name": "Producto sintético", "stock": {"on_hand": 15}, "coverage": {"days": "5.00", "basis": "actual_90d"},
    "demand": {"units": 84, "days": 28}, "forecast": {"daily_mean": "2.00", "days": 28}, "supplier": {"id": "sup-a"},
    "expiry_lots": [{"batch": "L1", "quantity": 10, "expiry_date": "2027-12-20", "band": "later"}, {"batch": "L2", "quantity": 5, "expiry_date": None, "band": "none"}],
    "states": ["cost_estimated"],
}
DRILL = {"kind": "expiry_band", "truncated": False, "total": 1, "offset": 0, "sum": "40.00", "rows": [{"variant_id": 4, "sku": "SYN-004", "name": "Sintético", "figure": "40.00"}]}
FRESH = {"sources": [{"source": "inventory_snapshot", "refreshed_at": "2026-11-09T08:00:00Z", "refreshed_at_original": None, "origin": "erp_sync", "state": "ok", "stale_after_hours": 48}],
         "excluded_records": 2, "local_load_excluded": 1, "review_list_link": "/calidad"}


@pytest.mark.parametrize("name", ["dashboard_sku", "dashboard_drilldown", "dashboard_freshness"])
def test_each_schema_is_valid_and_has_its_own_id(name):
    jsonschema.Draft202012Validator.check_schema(load(name))
    assert load(name)["$id"] == f"mmi/dto/{name}.v1"


def test_a_sku_page_with_and_without_cost_is_accepted():
    validate("dashboard_sku", SKU)
    validate("dashboard_sku", {**SKU, "cost": {"value": "40.00", "estimated": False, "unit_cost": "2.00"}})
    validate("dashboard_sku", {**SKU, "name": None, "stock": {"on_hand": None}, "coverage": None, "forecast": None, "supplier": None, "expiry_lots": [], "states": []})


def test_a_sku_page_refuses_internal_ids_unknown_bands_and_unknown_states():
    for bad in ({**SKU, "variant_id": 1}, {**SKU, "expiry_lots": [{**SKU["expiry_lots"][0], "band": "soon"}]}, {**SKU, "states": ["mystery"]},
                {**SKU, "coverage": {"days": "5,00", "basis": "actual_90d"}}, {**SKU, "cost": {"value": "40.00"}}):
        with pytest.raises(jsonschema.ValidationError):
            validate("dashboard_sku", bad)
    missing = copy.deepcopy(SKU)
    del missing["expiry_lots"]
    with pytest.raises(jsonschema.ValidationError):
        validate("dashboard_sku", missing)


@pytest.mark.parametrize("kind", ["inventory_value", "coverage", "stockout_risk", "expiry_risk", "abc_xyz", "trend_day", "demand", "forecast", "capital", "expiry_band"])
def test_every_drilldown_kind_is_accepted(kind):
    validate("dashboard_drilldown", {**DRILL, "kind": kind})


def test_a_viewer_page_with_null_amounts_is_accepted_and_the_deferred_budget_kind_is_refused():
    validate("dashboard_drilldown", {**DRILL, "sum": None, "rows": [{**DRILL["rows"][0], "figure": None}]})
    for bad in ({**DRILL, "kind": "budget"}, {**DRILL, "total": -1}, {**DRILL, "sum": "40,00"}, {**DRILL, "rows": [{**DRILL["rows"][0], "notes": "x"}]}):
        with pytest.raises(jsonschema.ValidationError):
            validate("dashboard_drilldown", bad)


def test_freshness_uses_the_indicator_vocabulary_and_refuses_the_old_one():
    validate("dashboard_freshness", FRESH)
    for state in ("no_data", "stale", "error"):
        validate("dashboard_freshness", {**FRESH, "sources": [{**FRESH["sources"][0], "state": state}]})
    for bad_state in ("fresh", "failed", "empty"):
        with pytest.raises(jsonschema.ValidationError):
            validate("dashboard_freshness", {**FRESH, "sources": [{**FRESH["sources"][0], "state": bad_state}]})
    with pytest.raises(jsonschema.ValidationError):
        validate("dashboard_freshness", {**FRESH, "excluded_records": -1})
    with pytest.raises(jsonschema.ValidationError):
        validate("dashboard_freshness", {k: v for k, v in FRESH.items() if k != "local_load_excluded"})
