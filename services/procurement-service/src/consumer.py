"""T146 / T148 / T149 / T150: the procurement-in queue consumer and the receipt poll.

* siweb.cost.write_completed.v1  -> record the writer's outcome on the cost write request
* forecast.completed.v1          -> remember the latest run (freshness) for the proposal screen and alerts
* siweb.sync.completed.v1        -> kind "supplier_costs": ingest ERP supplier rows; every other kind is acknowledged
* inventory.snapshot.created.v1  -> acknowledged (stock is read on demand when a proposal is generated)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from costs.recargo import load_table
from costs.rules import load_rules
from costs.siweb_import import import_supplier_rows
from costs.writes import WriteError, apply_outcome
from db.tables import forecast_runs_seen, inbox, receipt_cursor
from mmi_common.bus import MessageBus
from mmi_common.dispatch import BlobReader, DispatchStats, Handler, RejectMessageError, consume_queue
from orders.reconcile import Receipt, reconcile_receipts
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine

QUEUE = "procurement-in"
WRITE_COMPLETED = "siweb.cost.write_completed.v1"
FORECAST = "forecast.completed.v1"
SYNC = "siweb.sync.completed.v1"
SNAPSHOT = "inventory.snapshot.created.v1"


def supplier_rows_from_payload(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise ERP supplier rows (purchase_cost_cents may be fractional); the tax identifier is never read."""
    rows = []
    for r in doc.get("records", []):
        cents = r.get("purchase_cost_cents")
        rows.append({"product_id": int(r["product_id"]), "contact_id": int(r["contact_id"]), "supplier_name": r.get("supplier_name"),
                     "purchase_cost": None if cents is None else Decimal(str(cents)) / 100, "currency": r.get("currency") or "EUR",
                     "lead_time_days": r.get("lead_time_days"), "min_order_qty": r.get("min_order_qty")})
    return rows


@dataclass
class ProcurementConsumer:
    now: datetime | None = None

    def handlers(self) -> dict[str, Handler]:
        def completed(conn: Connection, env: dict[str, Any], payload: bytes) -> None:
            doc = json.loads(payload)
            try:
                apply_outcome(conn, doc["cost_write_request_id"], doc["outcome"], int(doc.get("attempts", 0)), doc.get("error"), self.now)
            except (WriteError, KeyError) as exc:
                raise RejectMessageError from exc

        def forecast(conn: Connection, env: dict[str, Any], payload: bytes) -> None:
            doc = json.loads(payload)
            if conn.execute(select(forecast_runs_seen.c.run_id).where(forecast_runs_seen.c.run_id == doc["run_id"])).first() is None:
                conn.execute(insert(forecast_runs_seen).values(run_id=doc["run_id"], input_hash=doc["input_hash"], eligible_count=int(doc["eligible_count"]),
                                                               received_at=self.now or datetime.now(UTC)))

        def sync(conn: Connection, env: dict[str, Any], payload: bytes) -> None:
            doc = json.loads(payload)
            if doc.get("kind") != "supplier_costs":
                return
            import_supplier_rows(conn, supplier_rows_from_payload(doc), load_rules(conn), load_table(conn), self.now)

        def ack(conn: Connection, env: dict[str, Any], payload: bytes) -> None:
            return None

        return {WRITE_COMPLETED: completed, FORECAST: forecast, SYNC: sync, SNAPSHOT: ack}


def consume_once(engine: Engine, bus: MessageBus, blobs: BlobReader, queue: str = QUEUE, now: datetime | None = None) -> DispatchStats:
    return consume_queue(engine, bus, blobs, queue, inbox, ProcurementConsumer(now).handlers(), now)


class ReceiptSource(Protocol):
    def fetch_after(self, after_id: int) -> list[dict[str, Any]]: ...


def sync_receipts(conn: Connection, source: ReceiptSource, now: datetime | None = None) -> dict[str, int]:
    """Poll inventory-service for supplier receipts after the cursor, match them to confirmed orders, advance the cursor."""
    row = conn.execute(select(receipt_cursor.c.last_movement_id).where(receipt_cursor.c.id == 1)).first()
    after = int(row.last_movement_id) if row else 0
    items = source.fetch_after(after)
    if not items:
        return {"fetched": 0, "matched": 0, "unmatched": 0, "excess": 0}
    res = reconcile_receipts(conn, [Receipt(int(x["movement_id"]), int(x["variant_id"]), int(x["qty"]), x.get("reference")) for x in items], now)
    newest = max(int(x["movement_id"]) for x in items)
    if row is None:
        conn.execute(insert(receipt_cursor).values(id=1, last_movement_id=newest))
    else:
        conn.execute(update(receipt_cursor).where(receipt_cursor.c.id == 1).values(last_movement_id=newest))
    return {"fetched": len(items), "matched": res.matched, "unmatched": len(res.unmatched), "excess": len(res.excess)}
