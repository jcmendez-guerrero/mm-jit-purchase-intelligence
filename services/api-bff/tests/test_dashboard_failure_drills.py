"""Feature 014 (T050, US6, SC-006): failure drills. A stale, failed or empty source shows an explicit state; nothing turns into a silent zero; the other cards stay correct."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest
from test_dashboard_orchestration import call, inventory
from tests_support import headers_for

REQ = httpx.Request("GET", "http://inventory/secret-host-name")
CARDS = {"/dashboard/summary": {"inventory_value": "100.00"}, "/dashboard/demand-trend": {"series": []}, "/dashboard/abc-xyz": {"cells": []}, "/risk": [],
         "/dashboard/filters/options": {"warehouses": []}}
KEYS = ["summary", "trend", "abc_xyz", "risks", "options"]
PATHS = ["/dashboard/summary", "/dashboard/demand-trend", "/dashboard/abc-xyz", "/risk", "/dashboard/filters/options"]


def failing(status=None, transport=False):
    return httpx.ConnectError("secret-host-name refused") if transport else httpx.HTTPStatusError("secret-host-name 500 trace", request=REQ, response=httpx.Response(status, request=REQ, text="Traceback secret-host-name"))


@pytest.mark.parametrize("which", range(5))
@pytest.mark.parametrize(("error", "code"), [(failing(503), "downstream_unavailable"), (failing(404), "downstream_refused"), (failing(transport=True), "downstream_unavailable")])
def test_each_failing_card_is_an_explicit_error_with_a_stable_code_and_no_downstream_text(role_store, which, error, code):
    inv = inventory(**{**CARDS, PATHS[which]: error})
    res = call("/api/dashboard/overview", headers_for("v", ["viewer"]), inv)
    body = res.json()
    assert res.status_code == 200 and body[KEYS[which]] == {"ok": False, "error": code}
    assert all(body[k]["ok"] is True for i, k in enumerate(KEYS) if i != which)                       # the others stay correct
    assert "secret-host-name" not in json.dumps(body) and "Traceback" not in json.dumps(body)


def test_when_inventory_is_down_its_indicators_are_errors_with_no_value_and_the_other_services_still_answer(role_store):
    inv = AsyncMock()
    inv.forward.side_effect = failing(503)
    proc = AsyncMock()
    proc.forward.side_effect = lambda m, path, **kw: [] if path == "/suppliers" else {"total": "0.00", "by_supplier": [], "range": {"budget": None, "proposed": "0.00", "spend": "0.00", "weeks": []}}
    rows = {i["key"]: i for i in call("/api/dashboard/overview", headers_for("v", ["buyer"]), inv, proc).json()["indicators"]}
    for key in ("stock_value", "coverage_days", "demand", "forecast", "stockout_risk", "expiry_exposure", "capital_tied_up"):
        assert rows[key]["state"] == "error" and rows[key]["value"] is None, key
    assert rows["purchasing_budget"]["state"] == "no_data" and rows["purchasing_budget"]["value"] is None        # no cap in force: "no budget", never a zero


def indicator(key, state, value):
    return {"key": key, "value": value, "unit": "EUR", "state": state, "basis": "dashboard.basis.lot_cost", "definition_key": f"dashboard.def.{key}",
            "freshness": {"source": "inventory_snapshot", "refreshed_at": None, "refreshed_at_original": None, "origin": "erp_sync", "state": state, "stale_after_hours": 48}}


def test_a_stale_indicator_reaches_the_screen_as_stale_with_its_value_and_an_empty_one_stays_no_data(role_store):
    inv = inventory(**{**CARDS, "/dashboard/indicators": {"filters": {}, "indicators": [indicator("stock_value", "stale", "100.00"), indicator("coverage_days", "no_data", None)]}})
    rows = {i["key"]: i for i in call("/api/dashboard/overview", headers_for("v", ["buyer"]), inv).json()["indicators"]}
    assert rows["stock_value"]["state"] == "stale" and rows["stock_value"]["value"] == "100.00"
    assert rows["coverage_days"]["state"] == "no_data" and rows["coverage_days"]["value"] is None


def test_no_indicator_is_ever_a_zero_when_its_source_has_nothing(role_store):
    rows = call("/api/dashboard/overview", headers_for("v", ["viewer"]), inventory(**CARDS)).json()["indicators"]
    assert len(rows) == 10
    assert all(r["value"] not in ("0", "0.00", 0) for r in rows if r["state"] in ("error", "no_data"))


def test_the_freshness_route_degrades_to_a_clear_error_and_leaks_nothing(role_store):
    inv = inventory(**{"/dashboard/freshness": failing(503)})
    res = call("/api/dashboard/freshness", headers_for("v", ["viewer"]), inv)
    assert res.status_code == 502 and res.json()["detail"] == "downstream_unavailable" and "secret-host-name" not in res.text
