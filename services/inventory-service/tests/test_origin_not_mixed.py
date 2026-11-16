"""T014b (inventory, FR-014, FR-023): a catalogue holding ERP products and locally loaded ones (surrogate ids from 9,000,000) keeps the origins apart."""

from datetime import date, timedelta

import quality_fixtures as qf
from conftest import auth
from db.tables import (
    ALL_WAREHOUSES,
    data_quality_snapshot,
    demand_observations,
    portfolio_aggregate,
    products,
    stock_history,
    variants,
)
from demand.provenance import SURROGATE_BASE
from sqlalchemy import insert, select
from test_quality_api import FROM, TO, seed_case

LOCAL_VARIANT = SURROGATE_BASE + 7


def seed_local(engine):
    """The 'smooth' fixture series again, but as a locally loaded product with a surrogate id and its own SKU."""
    s = qf.build_series("smooth")
    start = date.fromisoformat(s["start_day"])
    days = [start + timedelta(days=i) for i in range(len(s["demand"]))]
    with engine.begin() as c:
        c.execute(insert(products).values(external_id=LOCAL_VARIANT, name="Local", status="active", missed_syncs=0))
        c.execute(insert(variants).values(external_id=LOCAL_VARIANT, product_id=LOCAL_VARIANT, sku="EJ-9801", price=10))
        c.execute(insert(stock_history), [{"variant_id": LOCAL_VARIANT, "warehouse_id": ALL_WAREHOUSES, "day": d, "on_hand_reconstructed": 50, "censored": False, "reconciled_ok": True} for d in days])
        c.execute(insert(demand_observations), [{"variant_id": LOCAL_VARIANT, "warehouse_id": 1, "day": d, "demand_qty": q, "censored": False, "lineage": "x"}
                                                for d, q in zip(days, s["demand"], strict=True) if q != 0])
    return "EJ-9801"


def test_each_product_keeps_its_own_origin_in_snapshots_summaries_and_the_portfolio(client, engine):
    erp_sku, erp_id = seed_case(engine, "smooth")
    local_sku = seed_local(engine)
    assert client.post("/quality/recompute", headers=auth("buyer")).status_code == 200
    with engine.connect() as c:
        snaps = dict(c.execute(select(data_quality_snapshot.c.variant_id, data_quality_snapshot.c.origin)).all())
        rows = dict(c.execute(select(portfolio_aggregate.c.variant_id, portfolio_aggregate.c.origin)).all())
    assert snaps == {erp_id: "erp", LOCAL_VARIANT: "local_export"} and rows == snaps
    assert client.get(f"/quality/products/{erp_sku}?from={FROM}&to={TO}", headers=auth()).json()["origin"] == "erp"
    assert client.get(f"/quality/products/{local_sku}?from={FROM}&to={TO}", headers=auth()).json()["origin"] == "local_export"


def test_the_series_export_never_labels_local_data_as_observed(client, engine):
    seed_case(engine, "smooth")
    seed_local(engine)
    client.post("/quality/recompute", headers=auth("buyer"))
    labels = {s["variant_id"]: s["provenance"] for s in client.get("/export/series", headers=auth()).json()["series"]}
    assert labels[LOCAL_VARIANT] != "observed" and "observed" in labels.values()
