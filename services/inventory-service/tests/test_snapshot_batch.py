"""T094 (feature 018, FR-022): rebuilding the quality snapshots of the whole catalogue in batches gives exactly what the one-product path gives, and its
number of database statements does not grow with the number of products."""

from datetime import date, timedelta

import quality_fixtures as qf
from db.tables import (
    ALL_WAREHOUSES,
    anomaly_flags,
    data_quality_snapshot,
    demand_observations,
    products,
    stock_history,
    variants,
)
from quality.snapshot import build_snapshot, default_period, rebuild_snapshots
from sqlalchemy import delete, event, insert, select
from test_quality_api import seed_case

SNAPSHOT_COLUMNS = [c.name for c in data_quality_snapshot.c if c.name not in ("id", "built_at")]


def _stored(conn):
    snaps = [tuple(str(getattr(r, k)) for k in SNAPSHOT_COLUMNS) for r in conn.execute(select(data_quality_snapshot).order_by(data_quality_snapshot.c.variant_id)).all()]
    flags = [(r.variant_id, str(r.day), r.rule_id, str(r.original_value), r.decision) for r in conn.execute(select(anomaly_flags).order_by(anomaly_flags.c.variant_id, anomaly_flags.c.day, anomaly_flags.c.rule_id)).all()]
    return snaps, flags


def test_the_batch_path_stores_exactly_what_the_one_product_path_stores(engine):
    ids = [seed_case(engine, name)[1] for name in qf.CASES]
    with engine.begin() as c:
        for vid in ids:
            build_snapshot(c, vid, *default_period(c, vid))
        expected = _stored(c)
        assert expected[0] and expected[1]                                            # the fixtures include anomalies, gaps, stockouts and rejected rows
        c.execute(delete(data_quality_snapshot))
        c.execute(delete(anomaly_flags))
        assert rebuild_snapshots(c, ids) == len(ids)
        assert _stored(c) == expected


def test_a_second_batch_run_adds_nothing_and_keeps_buyer_decisions(engine):
    ids = [seed_case(engine, name)[1] for name in qf.CASES]
    with engine.begin() as c:
        rebuild_snapshots(c, ids)
        first = _stored(c)
        c.execute(anomaly_flags.update().where(anomaly_flags.c.rule_id == "mad_outlier").values(decision="accepted", decided_by="buyer-1"))
        rebuild_snapshots(c, ids)
        snaps, flags = _stored(c)
        assert [f for f in flags if f[2] == "mad_outlier"] and all(f[4] == "accepted" for f in flags if f[2] == "mad_outlier")
        assert len(flags) == len(first[1])                                            # no duplicate flags
        assert len(snaps) >= len(first[0])                                            # a changed decision may add a snapshot, never remove one


def test_the_number_of_statements_does_not_grow_with_the_products(engine):
    count = {"n": 0}

    @event.listens_for(engine, "before_cursor_execute")
    def _count(conn, cursor, statement, params, context, executemany):
        count["n"] += 1

    def seed(n):
        days = [date(2026, 1, 1) + timedelta(days=d) for d in range(30)]
        with engine.begin() as c:
            c.execute(insert(products), [{"external_id": i, "name": f"P{i}", "status": "active", "missed_syncs": 0} for i in range(1, n + 1)])
            c.execute(insert(variants), [{"external_id": i, "product_id": i, "sku": f"SYN-{i:04d}", "price": 5} for i in range(1, n + 1)])
            c.execute(insert(stock_history), [{"variant_id": i, "warehouse_id": ALL_WAREHOUSES, "day": d, "on_hand_reconstructed": 9, "censored": False, "reconciled_ok": True} for i in range(1, n + 1) for d in days])
            c.execute(insert(demand_observations), [{"variant_id": i, "warehouse_id": 1, "day": d, "demand_qty": 1 + (i + d.day) % 3, "censored": False, "lineage": "x"} for i in range(1, n + 1) for d in days])

    seed(300)
    with engine.begin() as c:
        before = count["n"]
        assert rebuild_snapshots(c, list(range(1, 301))) == 300
        used = count["n"] - before
    assert used < 60, f"{used} statements for 300 products"
