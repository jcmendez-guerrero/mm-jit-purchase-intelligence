"""Feature 014 (T033, US4): the analytical chart series. Synthetic reference dataset (TOTALS.md); every series has the frozen v2 ChartSeries shape and the rows add up to a card.

Expected figures (all warehouses, today 2026-11-09): stock value 100.00 = A 40.00 + B 20.00 + C 40.00; expiring value 60.00 = 20.00 in 0 to 30 days + 40.00 in 31 to 60 days.
Days of cover without a forecast: SYN-001 5, SYN-002 4, and three products without demand; with the daily means 2.0 / 0.5 / 1.0 for SYN-001 / 002 / 005: 7.5, 8 and 5.
"""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest
from conftest import auth
from dashboard.filters import FilterSet
from dashboard.kpis import compute_summary, refresh_aggregates
from dashboard.series import CHART_KEYS, build_charts
from db.tables import agg_daily_kpis
from reference_dataset import NOW, TODAY, freeze_clock, seed_reference
from sqlalchemy import insert, select

V2 = json.loads((Path(__file__).resolve().parents[3] / "packages" / "contracts" / "dto" / "dashboard_indicators.v2.schema.json").read_text(encoding="utf-8"))
D = Decimal
CHARTS_SCHEMA = json.loads((Path(__file__).resolve().parents[3] / "packages" / "contracts" / "dto" / "dashboard_charts.v1.schema.json").read_text(encoding="utf-8"))


class Means:
    def daily_means(self):
        return {1: 2.0, 2: 0.5, 5: 1.0}


def fs(**kw):
    return FilterSet.parse(TODAY, **kw)


def charts(engine, keys=CHART_KEYS, filters=None, money=True, forecast=None):
    with engine.connect() as c:
        out = build_charts(c, list(keys), TODAY, filters or fs(date_from=TODAY - timedelta(days=6)), forecast, money)
    return {x["key"]: x for x in out}


@pytest.fixture
def seeded(engine, monkeypatch):
    freeze_clock(monkeypatch)
    seed_reference(engine)
    with engine.begin() as c:
        refresh_aggregates(c, TODAY, None, NOW)
    return engine


def test_every_series_has_the_v2_chart_shape_and_the_keys_are_the_v2_keys(seeded):
    out = charts(seeded, forecast=Means())
    assert set(out) == set(CHART_KEYS) and set(CHART_KEYS) <= set(V2["$defs"]["ChartSeries"]["properties"]["key"]["enum"])
    for chart in out.values():
        jsonschema.validate(chart, {"$ref": "#/$defs/ChartSeries", "$defs": V2["$defs"]}, cls=jsonschema.Draft202012Validator)
        assert chart["state"] == "ok" and chart["rows"] and all(len(r) == len(chart["columns"]) for r in chart["rows"])


def test_at_least_five_charts_are_served():
    assert len(CHART_KEYS) >= 5


def test_expiry_bands_add_up_to_the_expiring_value_card(seeded):
    chart = charts(seeded)["expiry_bands"]
    assert chart["columns"] == ["band", "products", "value"]
    assert chart["rows"] == [["expired", 0, "0.00"], ["d0_30", 1, "20.00"], ["d31_60", 1, "40.00"]]
    with seeded.connect() as c:
        assert sum(D(r[2]) for r in chart["rows"]) == compute_summary(c, TODAY).expiring_value


def test_coverage_buckets_count_every_product_with_stock_once(seeded):
    plain = charts(seeded, ["coverage_buckets"])["coverage_buckets"]
    assert plain["columns"] == ["bucket", "products"]
    assert dict(plain["rows"]) == {"d0_7": 2, "d8_14": 0, "d15_30": 0, "d31_60": 0, "d61_plus": 0, "no_demand": 3}
    forecast = charts(seeded, ["coverage_buckets"], forecast=Means())["coverage_buckets"]
    assert dict(forecast["rows"]) == {"d0_7": 1, "d8_14": 2, "d15_30": 0, "d31_60": 0, "d61_plus": 0, "no_demand": 2}
    assert sum(r[1] for r in forecast["rows"]) == 5


def test_capital_by_group_adds_up_to_the_stock_value_and_names_what_it_leaves_out(seeded):
    chart = charts(seeded)["capital_by_group"]
    assert chart["columns"] == ["group", "products", "value"]
    assert chart["rows"] == [["A", 1, "40.00"], ["B", 2, "20.00"], ["C", 1, "40.00"]]
    assert chart["summary_params"]["part"] == "stock_at_cost"                      # the open orders belong to procurement and have no group rows
    with seeded.connect() as c:
        assert sum(D(r[2]) for r in chart["rows"]) == compute_summary(c, TODAY).inventory_value


def test_abc_xyz_follows_the_supplier_filter(seeded):
    everyone = charts(seeded, ["abc_xyz"])["abc_xyz"]
    only_a = charts(seeded, ["abc_xyz"], filters=fs(supplier_id="sup-a"))["abc_xyz"]
    assert everyone["columns"] == ["group", "products", "value"]
    assert sum(r[1] for r in only_a["rows"]) < sum(r[1] for r in everyone["rows"]) and sum(r[1] for r in only_a["rows"]) == 2


def test_demand_and_forecast_share_one_table_and_never_blend(seeded):
    chart = charts(seeded, ["demand_forecast"], forecast=Means())["demand_forecast"]
    assert chart["columns"] == ["day", "actual", "forecast_mean", "forecast_upper"]
    past = [r for r in chart["rows"] if r[1] is not None]
    future = [r for r in chart["rows"] if r[1] is None]
    assert len(past) == 7 and past[-1][0] == TODAY.isoformat() and past[-1][1] == 4          # the bar is the existing trend: a censored day still shows its quantity (the demand card leaves it out)
    assert len(future) == 28 and future[0][2] == "3.50" and all(r[2] is not None for r in future)
    assert all(r[2] is None for r in past)


def test_demand_without_a_forecast_keeps_the_actual_days_and_says_why(seeded):
    chart = charts(seeded, ["demand_forecast"])["demand_forecast"]
    assert chart["state"] == "ok" and all(r[2] is None for r in chart["rows"]) and chart["summary_params"]["forecast_reason"] == "no_forecast"


def test_stock_value_history_follows_the_stored_days_and_states_the_range(seeded):
    with seeded.begin() as c:
        for back, value in ((1, "90.00"), (2, "80.00"), (40, "10.00")):
            c.execute(insert(agg_daily_kpis).values(day=TODAY - timedelta(days=back), warehouse_id=None, category_id=None, inventory_value=D(value), refreshed_at=NOW))
    chart = charts(seeded, ["stock_value_history"], filters=fs(date_from=TODAY - timedelta(days=6)))["stock_value_history"]
    assert chart["columns"] == ["day", "value"] and [r[1] for r in chart["rows"]] == ["80.00", "90.00", "100.00"]
    assert chart["range_available"] == {"from": (TODAY - timedelta(days=40)).isoformat(), "to": TODAY.isoformat()}


def test_a_range_beyond_the_history_is_stated_not_padded(seeded):
    chart = charts(seeded, ["stock_value_history"], filters=fs(date_from=TODAY - timedelta(days=400), date_to=TODAY - timedelta(days=200)))["stock_value_history"]
    assert chart["state"] == "no_data" and chart["rows"] == [] and chart["summary_params"]["reason"] == "range_outside_history"
    assert chart["range_available"]["to"] == TODAY.isoformat()


def test_a_filter_the_history_does_not_store_says_so(seeded):
    chart = charts(seeded, ["stock_value_history"], filters=fs(supplier_id="sup-a"))["stock_value_history"]
    assert chart["state"] == "no_data" and chart["summary_params"]["reason"] == "filter_not_stored"


def test_a_role_without_cost_access_gets_no_money_column_and_no_value_history(seeded):
    out = charts(seeded, money=False)
    for key in ("expiry_bands", "capital_by_group", "abc_xyz"):
        assert "value" not in out[key]["columns"] and all(len(r) == len(out[key]["columns"]) for r in out[key]["rows"])
    assert out["stock_value_history"]["state"] == "no_data" and out["stock_value_history"]["summary_params"]["reason"] == "hidden_by_role"
    assert "40.00" not in json.dumps(out)


def test_an_empty_database_gives_no_data_for_every_chart_never_zero_rows(engine):
    out = charts(engine, forecast=None)
    assert all(c["state"] == "no_data" and c["rows"] == [] for c in out.values())


def test_the_retention_keeps_25_months_of_daily_history(engine):
    with engine.begin() as c:
        c.execute(insert(agg_daily_kpis).values(day=TODAY - timedelta(days=800), warehouse_id=None, category_id=None, inventory_value=D("1.00"), refreshed_at=NOW))
        c.execute(insert(agg_daily_kpis).values(day=TODAY - timedelta(days=700), warehouse_id=None, category_id=None, inventory_value=D("2.00"), refreshed_at=NOW))
        refresh_aggregates(c, TODAY, None, NOW)
        days = {r.day for r in c.execute(select(agg_daily_kpis.c.day)).all()}
    assert TODAY - timedelta(days=800) not in days and TODAY - timedelta(days=700) in days


def test_the_route_serves_the_charts_a_bad_key_is_refused_and_one_failure_does_not_stop_the_others(client, seeded, monkeypatch):
    ok = client.get("/dashboard/charts", params={"keys": "expiry_bands,coverage_buckets"}, headers=auth("buyer")).json()
    assert [c["key"] for c in ok["charts"]] == ["expiry_bands", "coverage_buckets"]
    jsonschema.validate(ok, CHARTS_SCHEMA, cls=jsonschema.Draft202012Validator)                                   # the real response matches its contract
    jsonschema.validate(client.get("/dashboard/charts", headers=auth("viewer")).json(), CHARTS_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert client.get("/dashboard/charts", params={"keys": "nope"}, headers=auth("buyer")).status_code == 422
    assert client.get("/dashboard/charts", headers=auth("buyer")).status_code == 200                       # no keys: all charts

    import dashboard.series as series

    monkeypatch.setitem(series.BUILDERS, "coverage_buckets", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = client.get("/dashboard/charts", params={"keys": "expiry_bands,coverage_buckets"}, headers=auth("buyer")).json()["charts"]
    assert out[0]["state"] == "ok" and out[1]["state"] == "error" and out[1]["rows"] == [] and "boom" not in json.dumps(out)


def test_a_viewer_gets_no_money_from_the_route(client, seeded):
    body = client.get("/dashboard/charts", headers=auth("viewer")).json()
    assert "40.00" not in json.dumps(body)


def test_a_single_day_of_history_is_one_row_and_a_730_day_range_keeps_every_stored_day(seeded):
    """T079 (feature 014): the edge cases "a single data point" and "a very long series"."""
    one = charts(seeded, ["stock_value_history"], filters=fs(date_from=TODAY - timedelta(days=6)))["stock_value_history"]
    assert [r[0] for r in one["rows"]] == [TODAY.isoformat()] and one["state"] == "ok"          # only today is stored: one point, not a padded week
    with seeded.begin() as c:
        c.execute(insert(agg_daily_kpis), [{"day": TODAY - timedelta(days=i), "warehouse_id": None, "category_id": None, "inventory_value": D(i), "refreshed_at": NOW} for i in range(1, 730)])
    long = charts(seeded, ["stock_value_history"], filters=fs(date_from=TODAY - timedelta(days=729)))["stock_value_history"]
    assert len(long["rows"]) == 730 and long["rows"][0][0] < long["rows"][-1][0]                  # complete and in order
    assert long["range_available"]["from"] == (TODAY - timedelta(days=729)).isoformat()
