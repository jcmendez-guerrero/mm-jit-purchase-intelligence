"""T174 (FR-007): every dashboard figure can be opened into the products behind it; the rows add up to the figure and respect the filters."""

from decimal import Decimal

import pytest
from conftest import auth
from dashboard.drilldown import DrillError, drilldown
from dashboard.kpis import Filters
from db.tables import products
from sqlalchemy import update
from test_aggregates import TODAY, Means, seed

D = Decimal


def rows(engine, kind, f=None, **kw):
    with engine.connect() as c:
        return drilldown(c, kind, TODAY, f or Filters(), **kw)


def ids(out):
    return [r["variant_id"] for r in out["rows"]]


def test_inventory_value_lists_variants_by_value_and_adds_up_to_the_kpi(engine):
    seed(engine)
    out = rows(engine, "inventory_value")
    assert [(r["variant_id"], r["figure"]) for r in out["rows"]] == [(1, "40.00"), (2, "12.00")]             # v3 has no cost: unvalued, not zero
    assert sum(D(r["figure"]) for r in out["rows"]) == D("52.00") and out["truncated"] is False
    assert out["rows"][0]["sku"] == "S1" and out["rows"][0]["name"] == "V1"


def test_coverage_lists_the_variants_with_the_fewest_days_first(engine):
    seed(engine)
    out = rows(engine, "coverage")
    assert [(r["variant_id"], r["figure"]) for r in out["rows"]] == [(2, "4.00"), (1, "5.00")]
    with engine.connect() as c:
        out = drilldown(c, "coverage", TODAY, Filters(), forecast=Means({1: 2.0}))
    assert [(r["variant_id"], r["figure"]) for r in out["rows"]] == [(2, "4.00"), (1, "7.50")]               # the forecast basis where eligible


def test_risk_kinds_list_exactly_the_flagged_variants_in_scope(engine):
    seed(engine)
    from risk.daily import evaluate_risks

    with engine.connect() as c:
        flagged = {t: sorted({r["variant_id"] for r in evaluate_risks(c, as_of=TODAY, expiry_horizon_days=60) if r["risk_type"] == t}) for t in ("stockout", "expiry")}
    assert sorted(ids(rows(engine, "stockout_risk"))) == flagged["stockout"]
    assert sorted(ids(rows(engine, "expiry_risk"))) == flagged["expiry"] and 1 in flagged["expiry"]            # v1 L2 expires within 60 days


def test_an_abc_xyz_cell_lists_its_variants_by_value(engine):
    seed(engine)
    assert ids(rows(engine, "abc_xyz", abc="B", xyz="Y")) == [2, 3] and ids(rows(engine, "abc_xyz", abc="A", xyz="X")) == [1]
    assert ids(rows(engine, "abc_xyz", abc="C", xyz="Z")) == []                                              # an empty cell is an empty list


def test_a_trend_day_lists_the_variants_with_the_most_units_that_day(engine):
    seed(engine)
    out = rows(engine, "trend_day", day=TODAY.isoformat())
    assert [(r["variant_id"], r["figure"]) for r in out["rows"]] == [(1, "3"), (2, "1")]


def test_filters_narrow_the_rows_like_the_kpis(engine):
    seed(engine)
    assert ids(rows(engine, "inventory_value", Filters(warehouse_id=2))) == [1]                              # only v1 L2 is in warehouse 2
    assert ids(rows(engine, "inventory_value", Filters(category="A"))) == [1]
    with engine.begin() as c:
        c.execute(update(products).where(products.c.external_id == 6).values(family="Familia sintética B"))
    assert ids(rows(engine, "abc_xyz", Filters(family="Familia sintética B"), abc="B", xyz="Y")) == [3]


def test_a_long_list_is_cut_and_says_so(engine):
    seed(engine)
    out = rows(engine, "inventory_value", limit=1)
    assert len(out["rows"]) == 1 and out["truncated"] is True


@pytest.mark.parametrize("kind,kw", [("nope", {}), ("abc_xyz", {}), ("abc_xyz", {"abc": "Q", "xyz": "X"}), ("trend_day", {}), ("trend_day", {"day": "yesterday"})])
def test_bad_requests_are_refused_with_a_code(engine, kind, kw):
    seed(engine)
    with pytest.raises(DrillError) as e, engine.connect() as c:
        drilldown(c, kind, TODAY, Filters(), **kw)
    assert e.value.code == "request_invalid"


def test_the_route_validates_and_requires_a_session(client, engine):
    seed(engine)
    assert client.get("/dashboard/drilldown?kind=abc_xyz&abc=B&xyz=Y").status_code == 401
    ok = client.get("/dashboard/drilldown?kind=abc_xyz&abc=B&xyz=Y", headers=auth()).json()
    assert ok["kind"] == "abc_xyz" and [r["variant_id"] for r in ok["rows"]] == [2, 3]
    assert client.get("/dashboard/drilldown?kind=nope", headers=auth()).status_code == 422
    assert client.get("/dashboard/drilldown?kind=trend_day&day=2026-13-40", headers=auth()).status_code == 422
