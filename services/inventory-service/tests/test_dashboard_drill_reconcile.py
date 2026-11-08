"""T036: drill-down rows add up to the figure on the card, pages never overlap, and ties are broken by SKU. Uses the synthetic reference dataset (TOTALS.md)."""

from decimal import Decimal

import pytest
from conftest import auth
from dashboard.drilldown import DrillError, drilldown
from dashboard.kpis import Filters, compute_summary, demand_trend
from reference_dataset import TODAY, seed_reference

D = Decimal


def drill(engine, kind, f=None, **kw):
    with engine.connect() as c:
        return drilldown(c, kind, TODAY, f or Filters(), **kw)


def test_the_sum_of_all_rows_equals_the_card_even_when_the_page_is_smaller(engine):
    seed_reference(engine)
    with engine.connect() as c:
        card = compute_summary(c, TODAY).inventory_value
    out = drill(engine, "inventory_value", limit=2)
    assert len(out["rows"]) == 2 and out["total"] == 4 and out["truncated"] is True
    assert D(out["sum"]) == card == D("100")


def test_pages_cover_every_row_once_and_in_a_stable_order(engine):
    seed_reference(engine)
    pages = [drill(engine, "inventory_value", limit=2, offset=o) for o in (0, 2, 4)]
    skus = [r["sku"] for p in pages for r in p["rows"]]
    assert skus == ["SYN-001", "SYN-004", "SYN-002", "SYN-005"]                 # 40 and 40 tie: SYN-001 before SYN-004; then 12, then 8
    assert [p["truncated"] for p in pages] == [True, False, False] and pages[2]["rows"] == [] and pages[1]["offset"] == 2


def test_a_supplier_filter_reconciles_with_its_card(engine):
    seed_reference(engine)
    f = Filters(supplier_id="sup-a")
    with engine.connect() as c:
        card = compute_summary(c, TODAY, f).inventory_value
    out = drill(engine, "inventory_value", f)
    assert [r["sku"] for r in out["rows"]] == ["SYN-001", "SYN-005"] and D(out["sum"]) == card == D("42")


def test_the_units_sold_on_a_day_add_up_to_the_trend_bar(engine):
    seed_reference(engine)
    day = TODAY.replace(day=TODAY.day - 1)
    with engine.connect() as c:
        bar = next(p["actual"] for p in demand_trend(c, TODAY, 7, Filters()) if p["day"] == day.isoformat())
    out = drill(engine, "trend_day", day=day.isoformat())
    assert int(out["sum"]) == bar == 4 and [r["sku"] for r in out["rows"]] == ["SYN-001", "SYN-002"]


def test_rows_always_carry_a_sku_for_the_screen_and_kinds_without_a_total_say_so(engine):
    seed_reference(engine)
    out = drill(engine, "coverage")
    assert out["sum"] is None and all(r["sku"] for r in out["rows"])


def test_a_negative_offset_is_refused(engine):
    seed_reference(engine)
    with pytest.raises(DrillError):
        drill(engine, "inventory_value", offset=-1)


def test_the_api_pages_and_returns_the_sum(client, engine):
    seed_reference(engine)
    res = client.get("/dashboard/drilldown?kind=inventory_value&limit=2&offset=2", headers=auth("buyer"))
    body = res.json()
    assert res.status_code == 200 and [r["sku"] for r in body["rows"]] == ["SYN-002", "SYN-005"] and body["sum"] == "100.00"
    assert client.get("/dashboard/drilldown?kind=inventory_value&offset=-1", headers=auth("buyer")).status_code == 422
