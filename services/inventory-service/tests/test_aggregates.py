"""T118 + T120 + T122: figures equal independently computed totals on a synthetic reference dataset."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from conftest import auth
from dashboard.kpis import Filters, compute_summary, demand_trend, refresh_aggregates
from db.tables import (
    ALL_WAREHOUSES,
    agg_daily_kpis,
    demand_observations,
    lot_cost_projection,
    product_segments,
    products,
    stock_lots,
    stock_snapshots,
    variants,
    warehouses,
)
from sqlalchemy import insert, select

D = Decimal
TODAY = date(2026, 11, 9)
NOW = datetime(2026, 11, 9, 8, tzinfo=UTC)


class Means:
    def __init__(self, m):
        self.m = m

    def daily_means(self):
        return self.m


def seed(engine):
    """Variants 1-3. Lots: v1 L1 qty 10 @2.00 and L2 qty 5 @4.00 (expires soon); v2 L9 qty 4 with no cost but v2 has another lot cost 3.00; v3 qty 6 with no cost at all."""
    with engine.begin() as c:
        c.execute(insert(products).values([{"external_id": 5, "name": "P", "status": "active", "missed_syncs": 0, "clinical_critical": False},
                                           {"external_id": 6, "name": "Q", "status": "active", "missed_syncs": 0, "clinical_critical": True}]))
        c.execute(insert(variants).values([{"external_id": 1, "product_id": 5, "sku": "S1", "name": "V1", "pack_size": 1, "uom": "u", "reorder_point": 2, "price": 99},
                                           {"external_id": 2, "product_id": 5, "sku": "S2", "name": "V2", "pack_size": 1, "uom": "u", "reorder_point": 2, "price": 99},
                                           {"external_id": 3, "product_id": 6, "sku": "S3", "name": "V3", "pack_size": 1, "uom": "u", "reorder_point": 2, "price": 99}]))
        c.execute(insert(warehouses).values([{"external_id": 1, "name": "Almacén sintético A", "is_unassigned": False}, {"external_id": 2, "name": "Almacén sintético B", "is_unassigned": False}]))
        soon, later = TODAY + timedelta(days=10), TODAY + timedelta(days=400)
        lots = [(1, 1, "L1", later, 10), (1, 2, "L2", soon, 5), (2, 1, "L9", later, 4), (3, 1, None, later, 6)]
        c.execute(insert(stock_lots).values([{"variant_id": v, "warehouse_id": w, "batch_number": b, "expiry_date": e, "quantity": q, "seen_at": NOW} for v, w, b, e, q in lots]))
        c.execute(insert(lot_cost_projection).values([
            {"variant_id": 1, "supplier_id": "s", "lot": "L1", "unit_cost": D("2.00"), "source": "confirmed_order", "updated_at": NOW},
            {"variant_id": 1, "supplier_id": "s", "lot": "L2", "unit_cost": D("4.00"), "source": "confirmed_order", "updated_at": NOW},
            {"variant_id": 2, "supplier_id": "s", "lot": "OLD", "unit_cost": D("3.00"), "source": "buyer_entry", "updated_at": NOW}]))
        snaps = [(1, ALL_WAREHOUSES, 15), (2, ALL_WAREHOUSES, 4), (3, ALL_WAREHOUSES, 6), (1, 1, 10), (1, 2, 5), (2, 1, 4), (3, 1, 6)]
        c.execute(insert(stock_snapshots).values([{"variant_id": v, "warehouse_id": w, "snapshot_date": TODAY, "on_hand": q, "available": q, "reserved": 0} for v, w, q in snaps]))
        c.execute(insert(product_segments).values([{"variant_id": 1, "abc": "A", "xyz": "X", "pattern": "smooth", "forecast_eligible": True, "reason": "", "metrics": {"value": 100}, "computed_at": NOW, "run_id": "r"},
                                                   {"variant_id": 2, "abc": "B", "xyz": "Y", "pattern": "smooth", "forecast_eligible": True, "reason": "", "metrics": {"value": 50}, "computed_at": NOW, "run_id": "r"},
                                                   {"variant_id": 3, "abc": "B", "xyz": "Y", "pattern": "lumpy", "forecast_eligible": False, "reason": "too_sparse", "metrics": {"value": 25}, "computed_at": NOW, "run_id": "r"}]))
        dem = []
        for i in range(90):                                               # v1: 3 a day for 90 days; v2: 1 a day; v3: no demand
            d = TODAY - timedelta(days=i)
            dem += [{"variant_id": 1, "warehouse_id": 1, "day": d, "demand_qty": 3, "censored": False, "lineage": "movements"},
                    {"variant_id": 2, "warehouse_id": 1, "day": d, "demand_qty": 1, "censored": i == 0, "lineage": "movements"}]
        c.execute(insert(demand_observations).values(dem))


def test_value_is_quantity_per_lot_times_lot_cost_with_labelled_fallback_and_unvalued_counted(engine):
    seed(engine)
    with engine.connect() as c:
        s = compute_summary(c, TODAY)
    # v1: 10*2 + 5*4 = 40 ; v2: 4*3 (fallback, estimated) = 12 ; v3: no cost -> unvalued, NOT zero-valued and never PVP (99)
    assert s.inventory_value == D("52") and s.valued_with_estimate == 1 and s.unvalued_lots == 1
    assert s.expiring_value == D("20.00")                                # only v1 L2 expires within 60 days: 5 x 4
    assert s.as_json()["value_basis"] == "lot_acquisition_cost"


def test_the_erp_price_never_enters_the_value(engine):
    seed(engine)
    with engine.begin() as c:
        c.execute(variants.update().values(price=D("1000000")))
    with engine.connect() as c:
        assert compute_summary(c, TODAY).inventory_value == D("52")


def test_coverage_uses_the_forecast_when_eligible_and_the_actual_average_otherwise_and_labels_the_basis(engine):
    seed(engine)
    with engine.connect() as c:
        s = compute_summary(c, TODAY, forecast=Means({1: 2.0}))
    # v1: 15 on hand / 2.0 forecast per day = 7.5 ; v2: 4 / (90 actual units / 90 days = 1) = 4 ; v3: no demand -> excluded and counted
    assert s.coverage_days_avg == D("5.75") and s.basis == {"forecast": 1, "actual_90d": 1} and s.variants_without_demand == 1


def test_without_a_forecast_every_variant_uses_the_actual_basis(engine):
    seed(engine)
    with engine.connect() as c:
        s = compute_summary(c, TODAY)
    assert s.basis == {"forecast": 0, "actual_90d": 2} and s.coverage_days_avg == D("4.5")        # v1: 15/3=5, v2: 4/1=4


def test_filters_by_warehouse_and_by_category_use_the_same_rules(engine):
    seed(engine)
    with engine.connect() as c:
        wh2 = compute_summary(c, TODAY, Filters(warehouse_id=2))
        cat_a = compute_summary(c, TODAY, Filters(category="A"))
        crit = compute_summary(c, TODAY, Filters(category="critical"))
        bad = compute_summary(c, TODAY, Filters(category="B"))
    assert wh2.inventory_value == D("20") and cat_a.inventory_value == D("40") and cat_a.variant_count == 1
    assert crit.variant_count == 1 and crit.unvalued_lots == 1 and crit.inventory_value == D("0")
    assert bad.inventory_value == D("12")


def test_the_trend_series_is_actual_erp_demand_only_and_flags_censored_rows(engine):
    seed(engine)
    with engine.connect() as c:
        t = demand_trend(c, TODAY, 7, Filters())
    assert len(t) == 7 and all(p["kind"] == "actual_erp" and p["actual"] == 4 for p in t) and t[-1]["censored_rows"] == 1


def test_refresh_stores_the_same_figures_for_company_warehouses_and_categories(engine):
    seed(engine)
    with engine.begin() as c:
        written = refresh_aggregates(c, TODAY, now=NOW)
        rows = c.execute(select(agg_daily_kpis).where(agg_daily_kpis.c.day == TODAY)).all()
        live = compute_summary(c, TODAY)
    assert written >= 15 + 1 and len(rows) == 3 * 5
    company = next(r for r in rows if r.warehouse_id is None and r.category_id is None)
    assert D(str(company.inventory_value)) == live.inventory_value == D("52")
    with engine.begin() as c:
        refresh_aggregates(c, TODAY, now=NOW)                              # running it again replaces the day's rows, never duplicates
        assert len(c.execute(select(agg_daily_kpis).where(agg_daily_kpis.c.day == TODAY)).all()) == 15


@pytest.fixture
def seeded_client(client, engine):
    seed(engine)
    return client


def test_the_api_serves_summary_trend_distribution_and_options_to_signed_in_users_only(seeded_client):
    c = seeded_client
    for path in ("/dashboard/summary", "/dashboard/demand-trend", "/dashboard/abc-xyz", "/dashboard/filters/options"):
        assert c.get(path).status_code == 401
    s = c.get("/dashboard/summary?category=A", headers=auth()).json()
    assert s["inventory_value"] is not None and s["value_basis"] == "lot_acquisition_cost" and s["forecast_available"] is False
    assert c.get("/dashboard/summary?category=Z", headers=auth()).status_code == 422
    assert {(x["abc"], x["xyz"]) for x in c.get("/dashboard/abc-xyz", headers=auth()).json()["cells"]} == {("A", "X"), ("B", "Y")}
    assert c.get("/dashboard/demand-trend?days=7", headers=auth()).json()["estimated"] == []


def test_the_summary_for_about_1000_variants_is_computed_well_inside_the_3_second_budget(engine):
    import time

    with engine.begin() as c:
        c.execute(insert(products).values(external_id=1, name="P", status="active", missed_syncs=0))
        c.execute(insert(variants).values([{"external_id": i, "product_id": 1, "sku": f"S{i}", "name": "V", "pack_size": 1, "uom": "u", "reorder_point": 2, "price": 5} for i in range(1, 1001)]))
        c.execute(insert(stock_lots).values([{"variant_id": i, "warehouse_id": 1, "batch_number": "L", "expiry_date": TODAY + timedelta(days=30 * (i % 20)), "quantity": 5, "seen_at": NOW} for i in range(1, 1001)]))
        c.execute(insert(lot_cost_projection).values([{"variant_id": i, "supplier_id": "s", "lot": "L", "unit_cost": D("2.00"), "source": "confirmed_order", "updated_at": NOW} for i in range(1, 1001)]))
        c.execute(insert(stock_snapshots).values([{"variant_id": i, "warehouse_id": ALL_WAREHOUSES, "snapshot_date": TODAY, "on_hand": 5, "available": 5, "reserved": 0} for i in range(1, 1001)]))
        demand = [{"variant_id": i, "warehouse_id": 1, "day": TODAY - timedelta(days=d), "demand_qty": 1, "censored": False, "lineage": "m"} for i in range(1, 1001) for d in range(0, 90, 6)]
        for start in range(0, len(demand), 1000):                # stay under SQLite's bound-variable limit on older builds
            c.execute(insert(demand_observations).values(demand[start:start + 1000]))
    t0 = time.perf_counter()
    with engine.connect() as c:
        s = compute_summary(c, TODAY)
    assert s.inventory_value == D("10000") and time.perf_counter() - t0 < 3.0
