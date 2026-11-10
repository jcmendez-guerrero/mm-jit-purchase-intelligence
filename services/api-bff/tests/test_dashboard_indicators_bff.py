"""T091 / T093 / T024 (FR-025, FR-026, FR-003, ADR-023): the gateway passes procurement's open-orders amount to inventory, which makes the capital total, and itself builds only
the budget indicator from procurement's range; WAPE and bias come as percentages from forecast-service. It does no money arithmetic.

A failing service leaves only its own indicators as ``error``; a role without cost access gets the money indicators hidden and no spend is requested.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import jsonschema
from fastapi.testclient import TestClient
from routes.api import get_inventory_client, get_procurement_client
from routes.dashboard import accuracy_indicators, budget_indicator
from routes.policies import get_forecast_client
from tests_support import headers_for

FRESH = {"source": "inventory_snapshot", "refreshed_at": "2026-11-09T08:00:00Z", "refreshed_at_original": None, "origin": "erp_sync", "state": "ok", "stale_after_hours": 48}


def stock_payload(value="100.00", state="ok"):
    return {"filters": {"date_from": "2026-09-11", "date_to": "2026-11-09"}, "indicators": [{"key": "stock_value", "value": value, "unit": "EUR", "state": state,
                                                                                            "basis": "dashboard.basis.lot_cost", "definition_key": "dashboard.def.stock_value", "freshness": FRESH}]}


# ---- T093: budget, WAPE and bias; T024: the overview returns all ten ---------------------------------------------------------------

SCHEMA = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "dto" / "dashboard_indicators.v2.schema.json"
KEYS = ["stock_value", "coverage_days", "demand", "forecast", "stockout_risk", "expiry_exposure", "capital_tied_up", "purchasing_budget", "wape", "bias"]
RANGE = {"date_from": "2026-10-26", "date_to": "2026-11-09", "budget": "961.90", "spend": "90.00", "proposed": "50.50", "open_orders": "30.00",
         "weeks": [{"week_start": "2026-10-26", "cap": "500.00", "proposed": "10.50", "spend": "90.00"}, {"week_start": "2026-11-02", "cap": "230.95", "proposed": "40.00", "spend": "0.00"}, {"week_start": "2026-11-09", "cap": "230.95", "proposed": "0.00", "spend": "0.00"}]}


def ok(data):
    return {"ok": True, "data": data}


def test_the_budget_is_the_sum_of_the_weekly_caps_with_a_part_per_week_and_the_spend(role_store):
    b = budget_indicator(ok({"open_orders": "30.00", "range": RANGE}), True)
    assert b["key"] == "purchasing_budget" and b["value"] == "961.90" and b["state"] == "ok" and b["unit"] == "EUR"
    assert [(p["key"], p["value"]) for p in b["parts"]] == [("cap_week", "500.00"), ("cap_week", "230.95"), ("cap_week", "230.95"), ("proposed", "50.50"), ("spend", "90.00")]
    assert b["parts"][0]["period"] == {"from": "2026-10-26", "to": "2026-11-01"}


def test_without_any_cap_the_budget_says_so_and_still_shows_the_spend(role_store):
    b = budget_indicator(ok({"range": {**RANGE, "budget": None, "weeks": [{**w, "cap": None} for w in RANGE["weeks"]]}}), True)
    assert b["state"] == "no_data" and b["value"] is None and b["basis"] == "dashboard.basis.no_budget" and [(p["key"], p["value"]) for p in b["parts"]] == [("proposed", "50.50"), ("spend", "90.00")]


def test_the_budget_is_hidden_without_cost_access_and_an_error_when_procurement_failed_or_sent_no_range(role_store):
    assert budget_indicator({"ok": False, "error": "hidden_by_role"}, False)["state"] == "hidden_by_role"
    assert budget_indicator({"ok": False, "error": "downstream_unavailable"}, True)["state"] == "error"
    assert budget_indicator(ok({"range": None}), True)["state"] == "error"


def test_wape_and_bias_are_percentages_from_the_overall_group_and_name_the_filters_they_cannot_follow(role_store):
    w, b = accuracy_indicators(ok({"metrics": {"all": {"wape": "0.2345", "bias": "-0.0512"}}, "percent": {"all": {"wape": "23.45", "bias": "-5.12"}}}), ["supplier", "category"])
    assert (w["key"], w["value"], w["unit"], w["state"]) == ("wape", "23.45", "percent", "ok") and (b["key"], b["value"]) == ("bias", "-5.12")
    assert w["filters_unsupported"] == ["supplier", "category"] and w["freshness"]["source"] == "accuracy"


def test_wape_and_bias_are_no_data_when_nothing_was_scored_and_an_error_when_forecast_failed(role_store):
    assert {i["state"] for i in accuracy_indicators(ok({"metrics": {}, "percent": {}}), [])} == {"no_data"}
    assert {i["state"] for i in accuracy_indicators({"ok": False, "error": "downstream_unavailable"}, [])} == {"error"}


def overview(roles, inv_payload, spend=None, acc=None, query=""):
    from main import app

    inv = AsyncMock()

    async def inv_forward(method, path, **kw):
        if isinstance(inv_payload, Exception):
            raise inv_payload
        return inv_payload if path == "/dashboard/indicators" else {}

    inv.forward.side_effect = inv_forward
    proc = AsyncMock()

    async def proc_forward(method, path, **kw):
        if path == "/suppliers":
            return []
        if isinstance(spend, Exception):
            raise spend
        return spend or {"open_orders": "30.00", "range": RANGE}

    proc.forward.side_effect = proc_forward
    fc = AsyncMock(forward=AsyncMock(return_value=acc or {"metrics": {}, "percent": {"all": {"wape": "20.00", "bias": "10.00"}}}))
    app.dependency_overrides[get_inventory_client] = lambda: inv
    app.dependency_overrides[get_procurement_client] = lambda: proc
    app.dependency_overrides[get_forecast_client] = lambda: fc
    try:
        return TestClient(app).get(f"/api/dashboard/overview{query}", headers=headers_for("u", roles)), inv, proc
    finally:
        app.dependency_overrides.clear()


def six(state="ok"):
    return stock_payload() | {"indicators": [{**stock_payload()["indicators"][0], "key": k, "state": state, "definition_key": f"dashboard.def.{k}", "unit": "EUR" if "value" in k or k in ("expiry_exposure", "capital_tied_up") else "count"}
                                             for k in KEYS[:7]]}


def test_the_overview_returns_all_ten_indicators_in_order_and_they_match_the_contract(role_store):
    res, inv, proc = overview(["buyer"], six(), query="?supplier_id=sup-a&days=15")
    body = res.json()
    assert [i["key"] for i in body["indicators"]] == KEYS
    jsonschema.validate({"filters": {"date_from": "2026-10-26", "date_to": "2026-11-09"}, "indicators": body["indicators"]}, json.loads(SCHEMA.read_text(encoding="utf-8")), cls=jsonschema.Draft202012Validator)
    ind_call = next(c for c in inv.forward.call_args_list if c.args[1] == "/dashboard/indicators")
    spend_call = next(c for c in proc.forward.call_args_list if c.args[1] == "/summary/spend")
    assert ind_call.kwargs["params"]["supplier_id"] == "sup-a" and spend_call.kwargs["params"]["supplier_id"] == "sup-a"
    assert (date_to := ind_call.kwargs["params"]["date_to"]) == spend_call.kwargs["params"]["date_to"] and ind_call.kwargs["params"]["date_from"] == spend_call.kwargs["params"]["date_from"] and date_to


def test_the_overview_viewer_gets_the_budget_hidden_by_the_gateway_and_no_spend_is_requested(role_store):
    body = overview(["viewer"], six())[0].json()
    by = {i["key"]: i for i in body["indicators"]}
    assert by["purchasing_budget"]["state"] == "hidden_by_role" and by["purchasing_budget"]["value"] is None


def test_when_inventory_fails_its_indicators_and_the_capital_are_errors_but_budget_and_accuracy_still_show(role_store):
    body = overview(["buyer"], httpx.ConnectError("down"))[0].json()
    by = {i["key"]: i for i in body["indicators"]}
    assert all(by[k]["state"] == "error" and by[k]["value"] is None for k in KEYS[:7]) and by["purchasing_budget"]["state"] == "ok" and by["wape"]["state"] == "ok"


# ---- T091 (ADR-023): the gateway passes the open orders to inventory, which makes the capital total ----------------------------------

def capital_call(res):
    return next(i for i in res.json()["indicators"] if i["key"] == "capital_tied_up")


def test_the_open_orders_amount_goes_to_inventory_as_procurement_sent_it_and_the_capital_comes_back_verbatim(role_store):
    inv_payload = six()
    inv_payload["indicators"] = [*inv_payload["indicators"][:6], {**inv_payload["indicators"][0], "key": "capital_tied_up", "value": "129.95", "definition_key": "dashboard.def.capital_tied_up"}]
    res, inv, proc = overview(["buyer"], inv_payload, {"open_orders": "29.95", "range": RANGE})
    call = next(c for c in inv.forward.call_args_list if c.args[1] == "/dashboard/indicators")
    assert call.kwargs["params"]["open_orders"] == "29.95"
    assert capital_call(res)["value"] == "129.95"
    assert [c.args[1] for c in proc.forward.call_args_list].count("/summary/spend") == 1


def test_when_procurement_fails_inventory_is_asked_without_open_orders_so_it_answers_error_itself(role_store):
    res, inv, _proc = overview(["buyer"], six(), httpx.ConnectError("down"))
    call = next(c for c in inv.forward.call_args_list if c.args[1] == "/dashboard/indicators")
    assert "open_orders" not in call.kwargs["params"]
    assert next(i for i in res.json()["indicators"] if i["key"] == "purchasing_budget")["state"] == "error"


def test_a_viewer_causes_no_procurement_spend_call_and_no_open_orders_parameter(role_store):
    _res, inv, proc = overview(["viewer"], six())
    assert all(c.args[1] != "/summary/spend" for c in proc.forward.call_args_list)
    assert "open_orders" not in next(c for c in inv.forward.call_args_list if c.args[1] == "/dashboard/indicators").kwargs["params"]


def test_the_gateway_routes_hold_no_decimal_float_or_rounding():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "src" / "routes" / "dashboard.py").read_text(encoding="utf-8")
    assert not any(token in text for token in ("Decimal", "float(", "round("))
