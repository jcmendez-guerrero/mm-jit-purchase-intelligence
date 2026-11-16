"""T023 (feature 006): the inventory indicators in the v2 shape: value, unit, state, basis, definition key, freshness and the count of what is left out.

Covers the seven indicators inventory owns (stock value, coverage, demand, forecast, stockout risk, expiry exposure and capital tied up, whose open-orders part
is passed in by the gateway because procurement owns it); budget, WAPE and bias come from other services. The gateway does no money arithmetic (ADR-023). Figures are the synthetic reference dataset (TOTALS.md).
"""

import json
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest
from conftest import auth
from dashboard.filters import FilterSet
from dashboard.indicators import build_indicators
from dashboard.kpis import refresh_aggregates
from reference_dataset import NOW, TODAY, freeze_clock, seed_reference

SCHEMA = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "dto" / "dashboard_indicators.v2.schema.json"
KEYS = ["stock_value", "coverage_days", "demand", "forecast", "stockout_risk", "expiry_exposure", "capital_tied_up"]
OPEN = Decimal("30.00")


class Means:
    def daily_means(self):
        return {1: 2.0, 2: 0.5, 5: 1.0}


def check(payload):
    jsonschema.validate(payload, json.loads(SCHEMA.read_text(encoding="utf-8")), cls=jsonschema.Draft202012Validator)


def by_key(payload):
    return {i["key"]: i for i in payload["indicators"]}


@pytest.fixture
def seeded(engine, monkeypatch):
    freeze_clock(monkeypatch)
    seed_reference(engine)
    with engine.begin() as c:
        refresh_aggregates(c, TODAY, None, NOW)
    return engine


def build(engine, roles=("buyer",), forecast=None, open_orders=OPEN, **filters):
    with engine.connect() as c:
        return build_indicators(c, TODAY, FilterSet.parse(TODAY, **filters), forecast, roles, open_orders, NOW)


def test_a_buyer_gets_the_seven_indicators_matching_the_reference_totals_and_the_contract(seeded):
    p = build(seeded, forecast=Means())
    check(p)
    i = by_key(p)
    assert list(i) == KEYS
    assert (i["stock_value"]["value"], i["stock_value"]["unit"], i["stock_value"]["state"]) == ("100.00", "EUR", "ok")
    assert i["stock_value"]["incomplete_count"] == 1                                   # one lot without a cost, counted and not valued at zero
    assert (i["expiry_exposure"]["value"], i["expiry_exposure"]["unit"]) == ("60.00", "EUR")
    assert (i["demand"]["value"], i["demand"]["unit"]) == ("239", "units") and i["demand"]["incomplete_count"] == 1      # one censored row left out
    assert (i["forecast"]["value"], i["forecast"]["unit"]) == ("98.00", "units") and i["forecast"]["incomplete_count"] == 2
    assert i["stockout_risk"]["unit"] == "count" and i["coverage_days"]["unit"] == "days"
    assert (i["capital_tied_up"]["value"], i["capital_tied_up"]["unit"], i["capital_tied_up"]["state"]) == ("130.00", "EUR", "ok")
    assert [(x["key"], x["value"]) for x in i["capital_tied_up"]["parts"]] == [("stock_at_cost", "100.00"), ("open_orders", "30.00")]
    assert p["filters"]["date_to"] == TODAY.isoformat() and p["filters"]["date_from"] == "2026-09-11"


def test_every_indicator_names_its_basis_definition_and_where_its_data_came_from(seeded):
    for ind in build(seeded, forecast=Means())["indicators"]:
        assert ind["basis"].startswith("dashboard.basis.") and ind["definition_key"] == f"dashboard.def.{ind['key']}"
        assert ind["freshness"]["origin"] in ("erp_sync", "local_load", "forecast") and ind["freshness"]["source"] in ("inventory_snapshot", "movements", "forecast")


def test_a_role_without_cost_access_gets_the_money_indicators_hidden_with_no_value(seeded):
    p = build(seeded, roles=("viewer",), forecast=Means())
    check(p)
    i = by_key(p)
    for k in ("stock_value", "expiry_exposure", "capital_tied_up"):
        assert i[k]["state"] == "hidden_by_role" and i[k]["value"] is None
    assert i["demand"]["value"] == "239" and i["stockout_risk"]["state"] == "ok"
    assert "100.00" not in json.dumps(p) and "60.00" not in json.dumps(p)


def test_filters_change_the_figures_and_the_forecast_says_why_it_cannot_follow_a_warehouse(seeded):
    sup = by_key(build(seeded, forecast=Means(), supplier_id="sup-a"))
    assert sup["stock_value"]["value"] == "42.00"
    wh = by_key(build(seeded, forecast=Means(), warehouse_id=2))
    assert wh["stock_value"]["value"] == "60.00" and wh["demand"]["state"] == "no_data" and wh["demand"]["value"] is None
    assert wh["forecast"]["state"] == "no_data" and wh["forecast"]["value"] is None and wh["forecast"]["filters_unsupported"] == ["warehouse"]


def test_without_a_forecast_the_forecast_indicator_is_no_data_not_zero(seeded):
    f = by_key(build(seeded))["forecast"]
    assert f["state"] == "no_data" and f["value"] is None


def test_an_empty_database_gives_no_data_everywhere_and_still_matches_the_contract(engine):
    p = build(engine)
    check(p)
    assert {i["state"] for i in p["indicators"]} <= {"no_data", "ok"} and by_key(p)["stock_value"]["state"] == "no_data" and by_key(p)["demand"]["value"] is None


def test_the_route_serves_the_same_payload_and_hides_money_from_a_viewer(client, seeded):
    buyer = client.get("/dashboard/indicators", headers=auth("buyer"))
    assert buyer.status_code == 200
    check(buyer.json())
    assert by_key(buyer.json())["stock_value"]["value"] == "100.00"
    viewer = client.get("/dashboard/indicators?supplier_id=sup-a", headers=auth("viewer")).json()
    assert by_key(viewer)["stock_value"]["state"] == "hidden_by_role" and viewer["filters"]["supplier_id"] == "sup-a"


def test_the_route_refuses_a_bad_range_and_unknown_category(client, seeded):
    for q in ("date_from=2026-11-09&date_to=2026-10-01", "date_from=2020-01-01", "category=Z", "date_from=nope"):
        assert client.get(f"/dashboard/indicators?{q}", headers=auth("buyer")).status_code == 422


def test_capital_is_the_exact_sum_and_names_the_filters_open_orders_cannot_follow(seeded):
    sup = by_key(build(seeded, open_orders=Decimal("29.95"), supplier_id="sup-a"))["capital_tied_up"]
    assert sup["value"] == "71.95" and "filters_unsupported" not in sup                    # 42.00 of that supplier's stock + 29.95
    for f in ({"warehouse_id": 2, "category": "A"}, {"category": "A"}, {"family": "x"}):        # T099: the orders cannot follow these, so no total is better than a mixed one
        other = by_key(build(seeded, open_orders=Decimal("29.95"), **f))["capital_tied_up"]
        assert other["value"] is None and other["state"] == "no_data" and other["filters_unsupported"] == [k.removesuffix("_id") for k in f]
        assert [x["key"] for x in other["parts"]] == ["stock_at_cost", "open_orders"] and other["parts"][1]["value"] == "29.95"


def test_without_the_open_orders_the_capital_is_an_error_with_no_partial_total(seeded):
    c = by_key(build(seeded, open_orders=None))["capital_tied_up"]
    assert c["state"] == "error" and c["value"] is None and "parts" not in c
    check(build(seeded, open_orders=None))


def test_the_route_takes_the_open_orders_and_refuses_a_bad_amount(client, seeded):
    ok = by_key(client.get("/dashboard/indicators?open_orders=29.95", headers=auth("buyer")).json())["capital_tied_up"]
    assert ok["value"] == "129.95"
    for bad in ("abc", "-1", "1e5", "1.234"):
        assert client.get(f"/dashboard/indicators?open_orders={bad}", headers=auth("buyer")).status_code == 422
    assert by_key(client.get("/dashboard/indicators", headers=auth("buyer")).json())["capital_tied_up"]["state"] == "error"
