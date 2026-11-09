"""T006: the dashboard indicators contract (feature 006, schema v2): valid payloads pass, invalid ones are refused, and v1 stays untouched.

Synthetic values only. Money and counts travel as decimal strings; every object is closed (no extra properties).
"""

import copy
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "dto" / "dashboard_indicators.v2.schema.json"
V1 = ROOT / "dto" / "dashboard_summary.v1.schema.json"
KEYS = ["stock_value", "coverage_days", "demand", "forecast", "stockout_risk", "expiry_exposure", "capital_tied_up", "purchasing_budget", "wape", "bias"]


def schema() -> dict:
    return json.loads(V2.read_text(encoding="utf-8"))


def validate(payload: object, name: str | None = None) -> None:
    s = schema()
    target = s if name is None else {"$ref": f"#/$defs/{name}", "$defs": s["$defs"]}
    jsonschema.validate(payload, target, cls=jsonschema.Draft202012Validator)


FRESH = {"source": "inventory_snapshot", "refreshed_at": "2026-11-09T08:00:00Z", "refreshed_at_original": None, "origin": "erp_sync", "state": "ok", "stale_after_hours": 48}


def indicator(key: str = "stock_value", **over) -> dict:
    return {"key": key, "value": "100.00", "unit": "EUR", "state": "ok", "basis": "dashboard.basis.lot_cost", "definition_key": f"dashboard.def.{key}", "freshness": FRESH, **over}


def payload(*indicators: dict) -> dict:
    return {"filters": {"date_from": "2026-09-11", "date_to": "2026-11-09"}, "indicators": list(indicators or [indicator()])}


def test_the_schema_is_valid_and_has_its_own_id():
    jsonschema.Draft202012Validator.check_schema(schema())
    assert schema()["$id"] == "mmi/dto/dashboard_indicators.v2"


def test_every_indicator_key_is_accepted():
    validate(payload(*[indicator(k) for k in KEYS]))


def test_capital_tied_up_carries_its_two_parts_and_the_budget_its_caps_and_spend():
    capital = indicator("capital_tied_up", value="130.00", parts=[
        {"key": "stock_at_cost", "label_key": "dashboard.part.stock_at_cost", "value": "100.00"},
        {"key": "open_orders", "label_key": "dashboard.part.open_orders", "value": "30.00"}])
    budget = indicator("purchasing_budget", value="900.00", parts=[
        {"key": "cap_week", "label_key": "dashboard.part.cap_week", "value": "500.00", "period": {"from": "2026-11-02", "to": "2026-11-08"}},
        {"key": "cap_month", "label_key": "dashboard.part.cap_month", "value": "400.00", "period": {"from": "2026-11-01", "to": "2026-11-30"}},
        {"key": "spend", "label_key": "dashboard.part.spend", "value": "310.50"}])
    validate(payload(capital, budget))


def test_hidden_empty_and_stale_states_are_accepted_with_a_null_value():
    for state in ("hidden_by_role", "no_data", "stale", "error"):
        validate(payload(indicator(value=None, state=state)))


def test_filters_support_every_dimension_and_unsupported_ones_are_named():
    p = payload(indicator(filters_unsupported=["supplier"], incomplete_count=2))
    p["filters"].update({"warehouse_id": 1, "supplier_id": "3f2b8c1e-5a4d-4e7b-9c10-1d2e3f4a5b6c", "category": "critical", "family": "Familia sintética"})
    validate(p)


@pytest.mark.parametrize("mutate", [
    lambda p: p["indicators"][0].__setitem__("key", "revenue"),
    lambda p: p["indicators"][0].__setitem__("value", "1.234,50"),
    lambda p: p["indicators"][0].__setitem__("value", 100.0),
    lambda p: p["indicators"][0].__setitem__("state", "unknown"),
    lambda p: p["indicators"][0].__setitem__("unit", "USD"),
    lambda p: p["indicators"][0].pop("freshness"),
    lambda p: p["indicators"][0].__setitem__("extra", 1),
    lambda p: p["indicators"][0]["freshness"].__setitem__("origin", "excel"),
    lambda p: p["indicators"][0].__setitem__("parts", [{"key": "x", "value": "1.00"}]),
    lambda p: p["filters"].__setitem__("category", "Z"),
    lambda p: p["filters"].pop("date_to"),
    lambda p: p.pop("indicators"),
])
def test_invalid_payloads_are_refused(mutate):
    p = copy.deepcopy(payload(indicator()))
    mutate(p)
    with pytest.raises(jsonschema.ValidationError):
        validate(p)


def test_a_drilldown_page_matches_the_contract_and_drift_is_refused():
    page = {"kind": "inventory_value", "rows": [{"variant_id": 1, "sku": "SYN-001", "name": "Variante sintética 1", "figure": "40.00"}],
            "total": 1, "truncated": False, "offset": 0, "sum": "40.00"}
    validate(page, "DrillPage")
    bad = copy.deepcopy(page)
    bad["rows"][0]["contribution"] = "1"
    with pytest.raises(jsonschema.ValidationError):
        validate(bad, "DrillPage")


def test_a_chart_series_matches_the_contract():
    validate({"key": "expiry_bands", "title_key": "dashboard.chart.expiry_bands", "columns": ["band", "value"], "rows": [["0-30", "20.00"]], "state": "ok",
              "range_available": {"from": "2026-10-01", "to": "2026-11-09"}}, "ChartSeries")


def test_version_one_stays_as_it_was_and_both_versions_coexist():
    assert V1.exists() and json.loads(V1.read_text(encoding="utf-8"))["$id"] == "mmi/dto/dashboard_summary.v1"
    assert json.loads((ROOT / "baseline" / "dto" / "dashboard_summary.v1.schema.json").read_text(encoding="utf-8")) == json.loads(V1.read_text(encoding="utf-8"))
