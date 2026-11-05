"""T148 / T150 / T149: the pipeline after a sync, the inbound projection, lots, the export endpoints and the worker."""

from datetime import UTC, datetime, timedelta

from conftest import auth
from db.tables import inbound_lines, outbox, product_segments, stock_history, stock_lots
from demand.publisher import SUBSCRIPTIONS, LocalBlobWriter
from generator import generate
from mmi_common.bus import POISON_SUFFIX
from projections.consumer import consume_once
from sqlalchemy import func, select
from worker import run_once

CID = "7d3b7c3e-1c0e-4f6a-9d58-0c7a1a2b3c4d"


def seed(publish, data):
    publish("products", [p for p in data.products if p["status"] == "active"])
    publish("variants", [{**v, "stock_total": 5} for v in data.variants])


def test_a_sync_triggers_rebuild_segments_and_both_events(engine, bus, blobs, publish, tmp_path):
    from demand.pipeline import Pipeline

    data = generate()
    seed(publish, data)
    publish("movements", data.movements)
    stats = consume_once(engine, bus, blobs, pipeline=Pipeline(LocalBlobWriter(tmp_path / "ev"), CID))
    assert stats.applied == 3 and stats.failed == 0
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(stock_history)).scalar_one() > 0 and c.execute(select(func.count()).select_from(product_segments)).scalar_one() > 0
        types = [r.type for r in c.execute(select(outbox)).all()]
    assert "inventory.snapshot.created.v1" in types and types.count("inventory.demand.updated.v1") >= 1


def test_reference_kinds_do_not_trigger_a_rebuild(engine, bus, blobs, publish, tmp_path):
    from demand.pipeline import Pipeline

    publish("warehouses", [{"id": 1, "name": "A"}])
    consume_once(engine, bus, blobs, pipeline=Pipeline(LocalBlobWriter(tmp_path), CID))
    with engine.connect() as c:
        assert c.execute(select(outbox)).all() == []


def test_lots_replace_the_stored_lots_of_the_variants_in_the_batch(engine, bus, blobs, publish):
    publish("lots", [{"variant_id": 1, "warehouse_id": 1, "batch_number": "L1", "expiry_date": "2027-05-01", "quantity": 4},
                     {"variant_id": 1, "warehouse_id": 1, "batch_number": "L2", "expiry_date": "bad-date", "quantity": 2},
                     {"variant_id": 2, "warehouse_id": None, "lot_number": "X", "expiry_date": None, "on_hand": 9}])
    consume_once(engine, bus, blobs)
    publish("lots", [{"variant_id": 1, "warehouse_id": 1, "batch_number": "L3", "expiry_date": "2027-06-01", "quantity": 7}])      # new picture of variant 1 only
    consume_once(engine, bus, blobs)
    with engine.connect() as c:
        rows = {(r.variant_id, r.batch_number): r for r in c.execute(select(stock_lots)).all()}
    assert set(rows) == {(1, "L3"), (2, "X")} and rows[(2, "X")].warehouse_id == 0 and rows[(2, "X")].quantity == 9


def test_a_malformed_lot_expiry_is_kept_without_an_expiry_not_dropped(engine, bus, blobs, publish):
    publish("lots", [{"variant_id": 1, "warehouse_id": 1, "batch_number": "L2", "expiry_date": "2027-13-40", "quantity": 2}])
    consume_once(engine, bus, blobs)
    with engine.connect() as c:
        r = c.execute(select(stock_lots)).one()
    assert r.quantity == 2 and r.expiry_date is None


def test_order_confirmed_projects_inbound_lines_idempotently(engine, bus, blobs, publish_event):
    publish_event("procurement.order.confirmed.v1", {"order_id": "o1", "proposal_id": "p1", "supplier_id": "s1",
                                                     "lines": [{"variant_id": 1, "qty": 10, "cost_with_recargo": "1.0"}, {"variant_id": 2, "qty": 0, "cost_with_recargo": "1"}]})
    consume_once(engine, bus, blobs)
    publish_event("procurement.order.confirmed.v1", {"order_id": "o1", "proposal_id": "p1", "supplier_id": "s1", "lines": [{"variant_id": 1, "qty": 12, "cost_with_recargo": "1.0"}]})
    consume_once(engine, bus, blobs)
    with engine.connect() as c:
        assert [(r.variant_id, r.qty) for r in c.execute(select(inbound_lines)).all()] == [(1, 12)]


def test_a_malformed_order_event_is_poisoned(engine, bus, blobs, publish_event):
    publish_event("procurement.order.confirmed.v1", {"proposal_id": "p1"})
    stats = consume_once(engine, bus, blobs)
    assert stats.rejected == 1 and bus.depth("inventory-in" + POISON_SUFFIX) == 1


def test_worker_pass_consumes_and_relays_every_event_to_its_subscribers(engine, bus, blobs, publish, tmp_path):
    data = generate()
    seed(publish, data)
    publish("movements", data.movements)
    out = run_once(engine, bus, blobs, LocalBlobWriter(tmp_path / "ev"), CID)
    assert out["applied"] == 3 and out["relayed"] >= 2 and out["failed"] == 0
    assert bus.depth("forecast-in") >= 1 and bus.depth("procurement-in") >= 1
    types = {m.body["type"] for m in bus.receive("forecast-in", 50)}
    assert "inventory.demand.updated.v1" in types and SUBSCRIPTIONS["inventory.demand.updated.v1"] == ["forecast-in"]
    with engine.connect() as c:
        assert all(r.status == "sent" for r in c.execute(select(outbox)).all())


def test_export_stock_and_receipts_endpoints(client, engine, bus, blobs, publish, tmp_path):
    from demand.pipeline import Pipeline

    data = generate()
    seed(publish, data)
    publish("movements", data.movements)
    publish("lots", [{"variant_id": 1, "warehouse_id": 1, "batch_number": "L1", "expiry_date": (datetime.now(UTC).date() + timedelta(days=5)).isoformat(), "quantity": 3}])
    consume_once(engine, bus, blobs, pipeline=Pipeline(LocalBlobWriter(tmp_path), CID))
    body = client.get("/export/stock", headers=auth()).json()
    v1 = next(v for v in body["variants"] if v["variant_id"] == 1)
    assert body["count"] == len(data.variants) and v1["on_hand"] == 5 and v1["lots"][0]["quantity"] == 3 and v1["segment"] is not None and v1["service_level"]
    r = client.get("/receipts?after_id=0&limit=50", headers=auth()).json()["receipts"]
    assert r and all(x["qty"] > 0 for x in r) and [x["movement_id"] for x in r] == sorted(x["movement_id"] for x in r)
    nxt = client.get(f"/receipts?after_id={r[-1]['movement_id']}&limit=50", headers=auth()).json()["receipts"]
    assert all(x["movement_id"] > r[-1]["movement_id"] for x in nxt)
    assert client.get("/export/stock").status_code == 401


def test_supplier_cost_syncs_are_acknowledged_and_ignored_by_inventory(engine, bus, blobs, publish):
    publish("supplier_costs", [{"product_id": 1, "contact_id": 9, "purchase_cost_cents": 100}])
    stats = consume_once(engine, bus, blobs)
    assert (stats.applied, stats.failed, stats.rejected) == (1, 0, 0)
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(stock_lots)).scalar_one() == 0


def test_lots_also_give_per_warehouse_snapshots_without_touching_the_company_wide_row(engine, bus, blobs, publish):
    from db.tables import ALL_WAREHOUSES, stock_snapshots

    publish("variants", [{"id": 1, "product_id": 1, "sku": "S", "name": "V", "stock_total": 9}])
    publish("lots", [{"variant_id": 1, "warehouse_id": 1, "batch_number": "A", "quantity": 4}, {"variant_id": 1, "warehouse_id": 1, "batch_number": "B", "quantity": 2},
                     {"variant_id": 1, "warehouse_id": 2, "batch_number": "C", "quantity": 3}])
    consume_once(engine, bus, blobs)
    with engine.connect() as c:
        snaps = {r.warehouse_id: r.on_hand for r in c.execute(select(stock_snapshots).where(stock_snapshots.c.variant_id == 1)).all()}
    assert snaps == {ALL_WAREHOUSES: 9, 1: 6, 2: 3}
    publish("lots", [{"variant_id": 1, "warehouse_id": 1, "batch_number": "A", "quantity": 1}])                  # a later picture replaces the day's per-warehouse rows
    consume_once(engine, bus, blobs)
    with engine.connect() as c:
        snaps = {r.warehouse_id: r.on_hand for r in c.execute(select(stock_snapshots).where(stock_snapshots.c.variant_id == 1)).all()}
    assert snaps == {ALL_WAREHOUSES: 9, 1: 1}
