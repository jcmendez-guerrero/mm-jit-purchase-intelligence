"""Feature 014 (T024, US3): the drill-down kinds added after PR 19 reconcile with their cards. Synthetic reference dataset (TOTALS.md).

``budget`` is not here: the caps and the spend belong to procurement and have no per-SKU rows in inventory (deferred, see the closure report).
"""

import json
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest
from dashboard.drilldown import DrillError, drilldown
from dashboard.kpis import Filters, compute_summary, demand_summary, forecast_summary
from dashboard.roles import hide_money_page
from reference_dataset import TODAY, seed_reference

D = Decimal
SCHEMA = json.loads((Path(__file__).resolve().parents[3] / "packages" / "contracts" / "dto" / "dashboard_drilldown.v1.schema.json").read_text(encoding="utf-8"))


class Means:
    def daily_means(self):
        return {1: 2.0, 2: 0.5, 5: 1.0}


def drill(engine, kind, f=None, **kw):
    with engine.connect() as c:
        return drilldown(c, kind, TODAY, f or Filters(), **kw)


def test_demand_rows_add_up_to_the_demand_card_and_leave_censored_days_out(engine):
    seed_reference(engine)
    with engine.connect() as c:
        card = demand_summary(c, TODAY, 60, Filters())["units"]
    out = drill(engine, "demand", days=60)
    assert [r["sku"] for r in out["rows"]] == ["SYN-001", "SYN-002"] and [r["figure"] for r in out["rows"]] == ["180", "59"]
    assert int(out["sum"]) == card == 239


def test_demand_follows_the_window_and_refuses_a_missing_or_absurd_one(engine):
    seed_reference(engine)
    assert int(drill(engine, "demand", days=7)["sum"]) == 7 * 3 + 7 * 1 - 1          # today's SYN-002 row is censored
    for bad in (None, 0, 731):
        with pytest.raises(DrillError):
            drill(engine, "demand", days=bad)


def test_forecast_rows_add_up_to_the_forecast_card(engine):
    seed_reference(engine)
    with engine.connect() as c:
        card = D(forecast_summary(c, TODAY, Filters(), Means())["units"])
    out = drill(engine, "forecast", forecast=Means())
    assert [r["sku"] for r in out["rows"]] == ["SYN-001", "SYN-005", "SYN-002"] and [r["figure"] for r in out["rows"]] == ["56.00", "28.00", "14.00"]
    assert D(out["sum"]) == card == D("98.00")


def test_without_a_forecast_the_forecast_kind_says_so_instead_of_listing_nothing(engine):
    seed_reference(engine)
    with pytest.raises(DrillError) as exc:
        drill(engine, "forecast")
    assert exc.value.code == "no_forecast"


def test_capital_lists_the_stock_part_and_matches_the_stock_value(engine):
    seed_reference(engine)
    with engine.connect() as c:
        stock = compute_summary(c, TODAY).inventory_value
    out = drill(engine, "capital")
    assert D(out["sum"]) == stock == D("100") and out["total"] == 4


@pytest.mark.parametrize(("band", "skus", "value"), [("expired", [], "0.00"), ("d0_30", ["SYN-001"], "20.00"), ("d31_60", ["SYN-004"], "40.00")])
def test_each_expiry_band_lists_its_lots_and_the_bands_add_up_to_the_card(engine, band, skus, value):
    seed_reference(engine)
    out = drill(engine, "expiry_band", band=band)
    assert [r["sku"] for r in out["rows"]] == skus and D(out["sum"]) == D(value)


def test_the_expiry_bands_together_equal_the_expiring_value(engine):
    seed_reference(engine)
    with engine.connect() as c:
        card = compute_summary(c, TODAY).expiring_value
    assert sum(D(drill(engine, "expiry_band", band=b)["sum"]) for b in ("expired", "d0_30", "d31_60")) == card == D("60")


def test_every_new_kind_returns_a_page_that_matches_the_contract_for_both_kinds_of_role(engine):
    seed_reference(engine)
    for kind, kw in (("demand", {"days": 60}), ("forecast", {"forecast": Means()}), ("capital", {}), ("expiry_band", {"band": "d0_30"})):
        page = drill(engine, kind, **kw)
        jsonschema.validate(page, SCHEMA, cls=jsonschema.Draft202012Validator)
        jsonschema.validate(hide_money_page(page, ["viewer"]), SCHEMA, cls=jsonschema.Draft202012Validator)


def test_an_unknown_band_is_refused(engine):
    seed_reference(engine)
    with pytest.raises(DrillError):
        drill(engine, "expiry_band", band="soon")


def test_a_viewer_gets_the_products_but_not_the_amounts_of_the_money_kinds(engine):
    seed_reference(engine)
    for kind, kw in (("capital", {}), ("expiry_band", {"band": "d31_60"})):
        page = hide_money_page(drill(engine, kind, **kw), ["viewer"])
        assert page["sum"] is None and all(r["figure"] is None and r["sku"] for r in page["rows"])


def test_the_route_serves_demand_for_the_card_window_and_hides_money_kinds_from_a_viewer(client, engine, monkeypatch):
    from conftest import auth
    from reference_dataset import freeze_clock

    freeze_clock(monkeypatch)
    seed_reference(engine)
    demand = client.get("/dashboard/drilldown", params={"kind": "demand", "date_from": "2026-09-11", "date_to": "2026-11-09"}, headers=auth("buyer")).json()
    assert int(demand["sum"]) == 239                                   # the 60-day window of the reference card
    assert client.get("/dashboard/drilldown", params={"kind": "demand"}, headers=auth("buyer")).status_code == 200
    money = client.get("/dashboard/drilldown", params={"kind": "capital"}, headers=auth("viewer")).json()
    assert money["sum"] is None and money["rows"]
    assert client.get("/dashboard/drilldown", params={"kind": "expiry_band", "band": "soon"}, headers=auth("buyer")).status_code == 422
