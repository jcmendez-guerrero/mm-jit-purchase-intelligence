"""T043/T044: projections and the inbox consumer, using the synthetic generator's dataset."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from db.tables import (
    ALL_WAREHOUSES,
    UNASSIGNED_WAREHOUSE,
    inbox,
    products,
    stock_movements,
    stock_snapshots,
    variants,
    warehouses,
)
from generator import generate
from mmi_common.bus import POISON_SUFFIX
from projections.consumer import consume_once
from sqlalchemy import func, select


@pytest.fixture(scope="module")
def data():
    return generate()


def load_reference(engine, bus, blobs, publish, data):
    publish("warehouses", data.warehouses)
    publish("products", [p for p in data.products if p["status"] == "active"])
    publish("variants", [{**v, "stock_total": 5} for v in data.variants])
    return consume_once(engine, bus, blobs, batch=10)


def test_reference_data_and_snapshots(engine, bus, blobs, publish, data):
    stats = load_reference(engine, bus, blobs, publish, data)
    assert stats.applied == 3 and stats.failed == stats.rejected == 0
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(warehouses)).scalar_one() == len(data.warehouses) + 1  # + unassigned
        assert c.execute(select(warehouses.c.is_unassigned).where(warehouses.c.external_id == UNASSIGNED_WAREHOUSE)).scalar_one()
        assert c.execute(select(func.count()).select_from(variants)).scalar_one() == len(data.variants)
        snap = c.execute(select(stock_snapshots)).first()
        assert snap.warehouse_id == ALL_WAREHOUSES and snap.on_hand == 5 and snap.available == 5
        assert c.execute(select(func.count()).select_from(products)).scalar_one() >= len({v["product_id"] for v in data.variants} & {p["id"] for p in data.products if p["status"] == "active"})


def test_movements_stored_once_with_quarantine_flag_and_decimal_cost(engine, bus, blobs, publish, data):
    load_reference(engine, bus, blobs, publish, data)
    quarantined = {m: ["x"] for m in data.truth["unreferenced_sale_ids"] + data.truth["malformed_expiry_ids"]}
    publish("movements", data.movements, quarantined=quarantined)
    consume_once(engine, bus, blobs)
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(stock_movements)).scalar_one() == len(data.movements)
        q = {r for r in c.execute(select(stock_movements.c.external_id).where(stock_movements.c.quarantined)).scalars()}
        assert q == set(quarantined)
        cost = c.execute(select(stock_movements.c.unit_cost).where(stock_movements.c.unit_cost.is_not(None))).scalars().first()
        assert isinstance(cost, Decimal | float) and cost > 0
        raw = c.execute(select(stock_movements.c.created_at_raw).limit(1)).scalar_one()
        assert "T" in raw  # original timestamp string preserved next to the UTC value
        assert c.execute(select(func.count()).select_from(stock_movements).where(stock_movements.c.warehouse_id == UNASSIGNED_WAREHOUSE)).scalar_one() > 0


def test_utc_conversion_uses_madrid_local_time(engine, bus, blobs, publish):
    publish("movements", [{"id": 1, "created_at": "2026-11-04T14:13:15.398297", "variant_id": 1, "warehouse_id": 1,
                           "quantity": 1, "reason": "return_customer"}])
    consume_once(engine, bus, blobs)
    with engine.connect() as c:
        r = c.execute(select(stock_movements.c.created_at_utc, stock_movements.c.created_at_raw)).one()
    assert r.created_at_utc.hour == 13 and r.created_at_raw == "2026-11-04T14:13:15.398297"  # CET = UTC+1


def test_resending_the_same_payload_is_idempotent(engine, bus, blobs, publish, data):
    env = publish("movements", data.movements[:300])
    consume_once(engine, bus, blobs)
    bus.send("inventory-in", env)          # redelivery of the same event_id
    stats = consume_once(engine, bus, blobs)
    assert stats.duplicates == 1 and stats.applied == 0
    publish("movements", data.movements[:300])         # a new event with overlapping rows
    consume_once(engine, bus, blobs)
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(stock_movements)).scalar_one() == 300
        assert c.execute(select(func.count()).select_from(inbox)).scalar_one() == 2


def test_checksum_mismatch_is_poisoned_not_applied(engine, bus, blobs, publish):
    publish("warehouses", [{"id": 1, "name": "A"}], tamper=True)
    stats = consume_once(engine, bus, blobs)
    assert stats.rejected == 1 and bus.depth("inventory-in") == 0
    assert bus.depth("inventory-in" + POISON_SUFFIX) == 1
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(warehouses)).scalar_one() == 0


def test_a_failing_handler_rolls_back_and_retries(engine, bus, blobs, publish):
    publish("movements", [{"id": 1, "created_at": "2026-03-01T10:00:00", "variant_id": 1, "warehouse_id": 1, "quantity": 1,
                           "reason": "purchase_receipt"}, {"id": 2, "variant_id": None, "quantity": "x", "reason": "r", "created_at": "x"}])
    stats = consume_once(engine, bus, blobs)
    assert stats.failed == 1
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(stock_movements)).scalar_one() == 0   # nothing half-applied
        assert c.execute(select(func.count()).select_from(inbox)).scalar_one() == 0            # registration rolled back
    assert bus.depth("inventory-in") == 1                                            # still queued for retry


def test_unknown_kind_is_not_silently_ignored(engine, bus, blobs, publish):
    publish("mystery", [])
    assert consume_once(engine, bus, blobs).failed == 1


def test_local_blob_reader_roundtrip(tmp_path):
    from projections.blob import LocalBlobReader

    p = Path(tmp_path / "x.json")
    p.write_text(json.dumps({"a": 1}))
    assert json.loads(LocalBlobReader().get(p.as_uri())) == {"a": 1}
