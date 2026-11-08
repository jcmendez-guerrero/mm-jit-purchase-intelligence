"""T148 (inventory part): data freshness per source, read by the admin status screen."""

from datetime import UTC, date, datetime

from conftest import auth
from db.tables import agg_daily_kpis, stock_movements, stock_snapshots
from sqlalchemy import insert


def test_reports_nothing_for_an_empty_store(client):
    body = client.get("/status/sources", headers=auth("admin")).json()
    assert body["stock_snapshots"] == {"latest_day": None, "rows": 0}
    assert body["movements"]["rows"] == 0 and body["movements"]["latest_at"] is None
    assert body["aggregates"]["refreshed_at"] is None


def test_reports_latest_days_counts_and_quarantine(client, engine):
    t = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
    with engine.begin() as c:
        c.execute(insert(stock_snapshots).values(variant_id=1, warehouse_id=1, snapshot_date=date(2026, 11, 3), on_hand=2, available=2, reserved=0))
        c.execute(insert(stock_snapshots).values(variant_id=1, warehouse_id=1, snapshot_date=date(2026, 11, 2), on_hand=2, available=2, reserved=0))
        for i, q in enumerate((False, True)):
            c.execute(insert(stock_movements).values(external_id=i + 1, created_at_utc=t, created_at_raw="x", variant_id=1, warehouse_id=1, quantity=1,
                                                     reason="purchase_receipt", has_note=False, quarantined=q))
        c.execute(insert(agg_daily_kpis).values(day=date(2026, 11, 3), inventory_value=0, refreshed_at=t))
    body = client.get("/status/sources", headers=auth("admin")).json()
    assert body["stock_snapshots"] == {"latest_day": "2026-11-03", "rows": 2}
    assert body["movements"] == {"rows": 2, "quarantined": 1, "latest_at": t.isoformat()}
    assert body["aggregates"]["refreshed_at"] == t.isoformat()


def test_is_admin_only(client):
    assert client.get("/status/sources").status_code == 401
    assert client.get("/status/sources", headers=auth("viewer")).status_code == 403
