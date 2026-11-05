"""Tests for daily risk evaluation (T112: stockout, expiry, data quality)."""

from datetime import UTC, date, datetime, timedelta

from conftest import auth
from db.tables import ALL_WAREHOUSES, products, stock_lots, stock_movements, stock_snapshots, variants
from risk.daily import evaluate_risks
from sqlalchemy import insert


def test_daily_risk_stockout_detection(engine):
    today = date(2026, 11, 4)
    with engine.begin() as conn:
        conn.execute(insert(products).values(external_id=1, name="Amoxicilina 500mg", status="active", missed_syncs=0, vat_rate=21.0))
        conn.execute(insert(variants).values(external_id=101, product_id=1, sku="AMX-500", name="Amoxicilina 500mg 20 comp", pack_size=1, uom="caja", reorder_point=10))
        # Available stock is 2, reorder point is 10 -> below reorder point / imminent stockout
        conn.execute(insert(stock_snapshots).values(
            variant_id=101, warehouse_id=ALL_WAREHOUSES, snapshot_date=today,
            on_hand=2, available=2, reserved=0,
        ))

    with engine.begin() as conn:
        risks = evaluate_risks(conn, as_of=today)

    stockout_risks = [r for r in risks if r["risk_type"] == "stockout"]
    assert len(stockout_risks) >= 1
    assert stockout_risks[0]["variant_id"] == 101
    assert "stockout" in stockout_risks[0]["explanation_key"]


def test_daily_risk_expiry_detection(engine):
    today = date(2026, 11, 4)
    with engine.begin() as conn:
        conn.execute(insert(products).values(external_id=2, name="Vacuna Puppy", status="active", missed_syncs=0, vat_rate=10.0))
        conn.execute(insert(variants).values(external_id=102, product_id=2, sku="VAC-PUP", name="Vacuna Puppy vial", pack_size=1, uom="vial"))
        # Lot expiring in 15 days
        conn.execute(insert(stock_lots).values(
            variant_id=102, warehouse_id=1, batch_number="LOT-2026-X",
            expiry_date=today + timedelta(days=15), quantity=50,
            seen_at=datetime.now(UTC),
        ))

    with engine.begin() as conn:
        risks = evaluate_risks(conn, as_of=today)

    expiry_risks = [r for r in risks if r["risk_type"] == "expiry" and r["variant_id"] == 102]
    assert len(expiry_risks) == 1
    assert expiry_risks[0]["explanation_key"] == "risk.expiry.near"
    assert expiry_risks[0]["params"]["batch_number"] == "LOT-2026-X"
    assert expiry_risks[0]["params"]["days_to_expiry"] == 15


def test_daily_risk_data_quality_detection(engine):
    today = date(2026, 11, 4)
    with engine.begin() as conn:
        conn.execute(insert(products).values(external_id=3, name="Antiparasitario", status="active", missed_syncs=0, vat_rate=None))
        conn.execute(insert(variants).values(external_id=103, product_id=3, sku="ANT-001", name="Antiparasitario pipetas", pack_size=3, uom="caja"))
        # Quarantined movement
        conn.execute(insert(stock_movements).values(
            external_id=9001, created_at_utc=datetime.now(UTC), created_at_raw="2026-11-04T10:00:00",
            variant_id=103, warehouse_id=1, quantity=10, reason="purchase_receipt",
            has_note=False, quarantined=True, quarantine_codes="malformed_expiry",
        ))

    with engine.begin() as conn:
        risks = evaluate_risks(conn, as_of=today)

    dq_risks = [r for r in risks if r["risk_type"] == "data_quality" and r["variant_id"] == 103]
    assert len(dq_risks) >= 1
    assert any("quarantined" in r["explanation_key"] for r in dq_risks)


def test_risk_endpoint_via_client(client, engine):
    today = date(2026, 11, 4)
    with engine.begin() as conn:
        conn.execute(insert(products).values(external_id=4, name="Colirio", status="active", missed_syncs=0, vat_rate=21.0))
        conn.execute(insert(variants).values(external_id=104, product_id=4, sku="COL-01", name="Colirio 10ml", pack_size=1, uom="frasco", reorder_point=5))
        conn.execute(insert(stock_snapshots).values(
            variant_id=104, warehouse_id=ALL_WAREHOUSES, snapshot_date=today,
            on_hand=0, available=0, reserved=0,
        ))

    res = client.get("/risk", headers=auth())
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    assert any(i["variant_id"] == 104 and i["risk_type"] == "stockout" for i in items)
