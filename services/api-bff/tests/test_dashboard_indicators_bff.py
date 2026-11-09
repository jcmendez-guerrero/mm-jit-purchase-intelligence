"""T091 (FR-025, FR-003): capital tied up = stock at lot cost (inventory) + confirmed orders not yet received (procurement), composed here with Decimal.

Both parts are returned; the total is their exact sum; when a part is missing or the role has no cost access there is no value, never a total made of one part.
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
RANGE = {"date_from": "2026-10-26", "date_to": "2026-11-09", "budget": "961.90", "spend": "140.50", "open_orders": "30.00",
         "weeks": [{"week_start": "2026-10-26", "cap": "500.00", "spend": "100.00"}, {"week_start": "2026-11-02", "cap": "230.95", "spend": "40.50"}, {"week_start": "2026-11-09", "cap": "230.95", "spend": "0.00"}]}


def ok(data):
    return {"ok": True, "data": data}


def test_the_budget_is_the_sum_of_the_weekly_caps_with_a_part_per_week_and_the_spend(role_store):
    b = budget_indicator(ok({"open_orders": "30.00", "range": RANGE}), True)
    assert b["key"] == "purchasing_budget" and b["value"] == "961.90" and b["state"] == "ok" and b["unit"] == "EUR"
    assert [(p["key"], p["value"]) for p in b["parts"]] == [("cap_week", "500.00"), ("cap_week", "230.95"), ("cap_week", "230.95"), ("spend", "140.50")]
    assert b["parts"][0]["period"] == {"from": "2026-10-26", "to": "2026-11-01"}


def test_without_any_cap_the_budget_says_so_and_still_shows_the_spend(role_store):
    b = budget_indicator(ok({"range": {**RANGE, "budget": None, "weeks": [{**w, "cap": None} for w in RANGE["weeks"]]}}), True)
    assert b["state"] == "no_data" and b["value"] is None and b["basis"] == "dashboard.basis.no_budget" and [p["key"] for p in b["parts"]] == ["spend"] and b["parts"][0]["value"] == "140.50"


def test_the_budget_is_hidden_without_cost_access_and_an_error_when_procurement_failed_or_sent_no_range(role_store):
    assert budget_indicator({"ok": False, "error": "hidden_by_role"}, False)["state"] == "hidden_by_role"
    assert budget_indicator({"ok": False, "error": "downstream_unavailable"}, True)["state"] == "error"
    assert budget_indicator(ok({"range": None}), True)["state"] == "error"


def test_wape_and_bias_are_percentages_from_the_overall_group_and_name_the_filters_they_cannot_follow(role_store):
    w, b = accuracy_indicators(ok({"metrics": {"all": {"wape": "0.2345", "bias": "-0.0512"}, "A": {"wape": "0.9"}}}), ["supplier", "category"])
    assert (w["key"], w["value"], w["unit"], w["state"]) == ("wape", "23.45", "percent", "ok") and (b["key"], b["value"]) == ("bias", "-5.12")
    assert w["filters_unsupported"] == ["supplier", "category"] and w["freshness"]["source"] == "accuracy"


def test_wape_and_bias_are_no_data_when_nothing_was_scored_and_an_error_when_forecast_failed(role_store):
    assert {i["state"] for i in accuracy_indicators(ok({"metrics": {}}), [])} == {"no_data"}
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
    fc = AsyncMock(forward=AsyncMock(return_value=acc or {"metrics": {"all": {"wape": "0.2", "bias": "0.1"}}}))
    app.dependency_overrides[get_inventory_client] = lambda: inv
    app.dependency_overrides[get_procurement_client] = lambda: proc
    app.dependency_overrides[get_forecast_client] = lambda: fc
    try:
        return TestClient(app).get(f"/api/dashboard/overview{query}", headers=headers_for("u", roles)), inv, proc
    finally:
        app.dependency_overrides.clear()


def six(state="ok"):
    return stock_payload() | {"indicators": [{**stock_payload()["indicators"][0], "key": k, "state": state, "definition_key": f"dashboard.def.{k}", "unit": "EUR" if "value" in k or k == "expiry_exposure" else "count"}
                                             for k in KEYS[:6]]}


def test_the_overview_returns_all_ten_indicators_in_order_and_they_match_the_contract(role_store):
    res, inv, proc = overview(["buyer"], six(), query="?supplier_id=sup-a&days=15")
    body = res.json()
    assert [i["key"] for i in body["indicators"]] == KEYS
    jsonschema.validate({"filters": {"date_from": "2026-10-26", "date_to": "2026-11-09"}, "indicators": body["indicators"]}, json.loads(SCHEMA.read_text(encoding="utf-8")), cls=jsonschema.Draft202012Validator)
    ind_call = next(c for c in inv.forward.call_args_list if c.args[1] == "/dashboard/indicators")
    spend_call = next(c for c in proc.forward.call_args_list if c.args[1] == "/summary/spend")
    assert ind_call.kwargs["params"]["supplier_id"] == "sup-a" and spend_call.kwargs["params"]["supplier_id"] == "sup-a"
    assert (date_to := ind_call.kwargs["params"]["date_to"]) == spend_call.kwargs["params"]["date_to"] and ind_call.kwargs["params"]["date_from"] == spend_call.kwargs["params"]["date_from"] and date_to


def test_the_overview_viewer_gets_no_money_indicator_with_a_value(role_store):
    body = overview(["viewer"], six())[0].json()
    by = {i["key"]: i for i in body["indicators"]}
    assert by["capital_tied_up"]["state"] == "hidden_by_role" and by["purchasing_budget"]["state"] == "hidden_by_role" and by["capital_tied_up"]["value"] is None


def test_when_inventory_fails_its_indicators_and_the_capital_are_errors_but_budget_and_accuracy_still_show(role_store):
    body = overview(["buyer"], httpx.ConnectError("down"))[0].json()
    by = {i["key"]: i for i in body["indicators"]}
    assert all(by[k]["state"] == "error" and by[k]["value"] is None for k in KEYS[:7]) and by["purchasing_budget"]["state"] == "ok" and by["wape"]["state"] == "ok"


# ---- T091 through the overview (the standalone capital route was removed by T094) -----------------------------------------------------

def capital_of(res):
    return next(i for i in res.json()["indicators"] if i["key"] == "capital_tied_up")


def test_the_capital_total_is_the_exact_sum_of_stock_at_cost_and_open_orders_and_both_parts_are_returned(role_store):
    c = capital_of(overview(["buyer"], six() | {"indicators": [{**i, "value": "100.10"} for i in six()["indicators"]]}, {"open_orders": "29.95", "range": RANGE})[0])
    assert c["state"] == "ok" and c["unit"] == "EUR" and c["value"] == "130.05" and c["definition_key"] == "dashboard.def.capital_tied_up"
    assert {p["key"]: p["value"] for p in c["parts"]} == {"stock_at_cost": "100.10", "open_orders": "29.95"} and c["freshness"]["source"] == "inventory_snapshot"


def test_filters_open_orders_cannot_follow_are_named_on_the_capital(role_store):
    res, _inv, proc = overview(["buyer"], six(), query="?supplier_id=sup-a&warehouse_id=2&category=A")
    assert capital_of(res)["filters_unsupported"] == ["warehouse", "category"]
    assert next(c for c in proc.forward.call_args_list if c.args[1] == "/summary/spend").kwargs["params"]["supplier_id"] == "sup-a"


def test_when_procurement_fails_the_capital_is_an_error_with_no_partial_total(role_store):
    c = capital_of(overview(["buyer"], six(), httpx.ConnectError("down"))[0])
    assert c["state"] == "error" and c["value"] is None and "parts" not in c


def test_a_missing_part_is_an_error_not_a_sum(role_store):
    no_stock = six() | {"indicators": [{**i, "value": None, "state": "no_data"} for i in six()["indicators"]]}
    assert capital_of(overview(["buyer"], no_stock)[0])["state"] == "error"
    assert capital_of(overview(["buyer"], six(), {"total": "1.00", "range": RANGE})[0])["state"] == "error"
