"""T044 / T148 / T150: the inventory-in queue consumer.

Handles siweb.sync.completed.v1 (apply the payload, then run the pipeline) and procurement.order.confirmed.v1 (project the
inbound order). Validation, dedup and poison handling are the shared dispatcher's.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from db.tables import inbound_lines, inbox
from demand.pipeline import Pipeline
from mmi_common.bus import MessageBus
from mmi_common.dispatch import BlobReader, DispatchStats, Handler, RejectMessageError, consume_queue
from mmi_common.time import ASSUMED_LOCAL_TZ
from sqlalchemy import delete, insert
from sqlalchemy.engine import Connection, Engine

from projections.apply import TOMBSTONE_AFTER_DEFAULT, apply_payload
from projections.lot_costs import apply_lot_cost

QUEUE = "inventory-in"
SYNC = "siweb.sync.completed.v1"
ORDER = "procurement.order.confirmed.v1"
LOT_COST = "procurement.lot_cost.changed.v1"
Stats = DispatchStats


def apply_order_confirmed(conn: Connection, doc: dict[str, Any], confirmed_at: datetime) -> int:
    """Replace the inbound lines of this order (idempotent per order)."""
    try:
        order_id, proposal_id, supplier_id = str(doc["order_id"]), str(doc["proposal_id"]), str(doc["supplier_id"])
        lines = list(doc.get("lines", []))
    except KeyError as exc:
        raise RejectMessageError from exc
    conn.execute(delete(inbound_lines).where(inbound_lines.c.order_id == order_id))
    rows = [{"order_id": order_id, "variant_id": int(x["variant_id"]), "proposal_id": proposal_id, "supplier_id": supplier_id, "qty": int(x["qty"]),
             "confirmed_at": confirmed_at} for x in lines if int(x["qty"]) > 0]
    if rows:
        conn.execute(insert(inbound_lines), rows)
    return len(rows)


@dataclass
class InventoryConsumer:
    pipeline: Pipeline | None = None
    tombstone_after: int = TOMBSTONE_AFTER_DEFAULT

    def handlers(self) -> dict[str, Handler]:
        def sync(conn: Connection, env: dict[str, Any], payload: bytes) -> None:
            occurred = datetime.fromisoformat(env["occurred_at"].replace("Z", "+00:00"))
            day = occurred.astimezone(ZoneInfo(ASSUMED_LOCAL_TZ)).date()
            doc = json.loads(payload)
            apply_payload(conn, doc, day, self.tombstone_after)
            if self.pipeline is not None:
                self.pipeline.after_sync(conn, doc["kind"], day)

        def order(conn: Connection, env: dict[str, Any], payload: bytes) -> None:
            occurred = datetime.fromisoformat(env["occurred_at"].replace("Z", "+00:00"))
            apply_order_confirmed(conn, json.loads(payload), occurred.astimezone(UTC))

        def lot_cost(conn: Connection, env: dict[str, Any], payload: bytes) -> None:
            occurred = datetime.fromisoformat(env["occurred_at"].replace("Z", "+00:00"))
            apply_lot_cost(conn, json.loads(payload), occurred.astimezone(UTC))

        return {SYNC: sync, ORDER: order, LOT_COST: lot_cost}


def consume_once(engine: Engine, bus: MessageBus, blobs: BlobReader, queue: str = QUEUE, batch: int = 10, tombstone_after: int = TOMBSTONE_AFTER_DEFAULT,
                 now: datetime | None = None, pipeline: Pipeline | None = None) -> DispatchStats:
    return consume_queue(engine, bus, blobs, queue, inbox, InventoryConsumer(pipeline, tombstone_after).handlers(), now, batch)
