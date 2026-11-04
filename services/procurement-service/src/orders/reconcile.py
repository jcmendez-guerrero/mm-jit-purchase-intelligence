"""T099: match later stock receipts to confirmed orders so inbound quantities are not double counted.

Receipt movements (reason purchase_receipt) reference the ERP purchase either as a plain id or as "Compra #n". When the buyer
linked an order to an ERP purchase number it matches exactly; otherwise receipts are matched first-in-first-out to the oldest
open order lines of the same variant. Each movement is applied once. Quantity beyond what was ordered is reported, never
silently added to an order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from db.tables import inbound_order_lines, inbound_orders, receipt_matches
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

_PLAIN = re.compile(r"^\s*(\d+)\s*$")
_COMPRA = re.compile(r"^\s*compra\s*#?\s*(\d+)\s*$", re.IGNORECASE)


def parse_purchase_ref(text: str | int | None) -> int | None:
    if text is None:
        return None
    if isinstance(text, int):
        return text
    m = _PLAIN.match(text) or _COMPRA.match(text)
    return int(m.group(1)) if m else None


@dataclass(frozen=True)
class Receipt:
    movement_id: int
    variant_id: int
    qty: int
    reference: str | int | None = None


@dataclass
class ReconcileResult:
    matched: int = 0
    already_applied: int = 0
    unmatched: list[tuple[int, str]] = field(default_factory=list)     # (movement_id, reason)
    excess: list[tuple[int, int]] = field(default_factory=list)        # (movement_id, units beyond the order)


def reconcile_receipts(conn: Connection, receipts: list[Receipt], now: datetime | None = None) -> ReconcileResult:
    now = now or datetime.now(UTC)
    res = ReconcileResult()
    for r in sorted(receipts, key=lambda x: x.movement_id):
        if r.qty <= 0:
            res.unmatched.append((r.movement_id, "not_a_receipt"))
            continue
        if conn.execute(select(receipt_matches.c.movement_id).where(receipt_matches.c.movement_id == r.movement_id)).first():
            res.already_applied += 1
            continue
        ref = parse_purchase_ref(r.reference)
        q = (select(inbound_order_lines, inbound_orders.c.confirmed_at, inbound_orders.c.erp_purchase_ref)
             .join(inbound_orders, inbound_orders.c.id == inbound_order_lines.c.order_id)
             .where(inbound_order_lines.c.variant_id == r.variant_id, inbound_order_lines.c.received_qty < inbound_order_lines.c.qty,
                    inbound_orders.c.status.in_(("confirmed", "partially_received")))
             .order_by(inbound_orders.c.confirmed_at, inbound_orders.c.id))
        candidates = conn.execute(q).all()
        exact = [c for c in candidates if ref is not None and c.erp_purchase_ref == ref]
        pool = exact or candidates
        if not pool:
            res.unmatched.append((r.movement_id, "no_open_order"))
            continue
        left, first_order = r.qty, None
        for line in pool:
            take = min(left, line.qty - line.received_qty)
            if take <= 0:
                continue
            conn.execute(update(inbound_order_lines).where(inbound_order_lines.c.order_id == line.order_id, inbound_order_lines.c.variant_id == line.variant_id)
                         .values(received_qty=line.received_qty + take))
            first_order = first_order or line.order_id
            left -= take
            _refresh_status(conn, line.order_id)
            if left == 0:
                break
        conn.execute(insert(receipt_matches).values(movement_id=r.movement_id, order_id=first_order, variant_id=r.variant_id, qty=r.qty - left, matched_at=now))
        if left:
            res.excess.append((r.movement_id, left))
        res.matched += 1
    return res


def _refresh_status(conn: Connection, order_id: str) -> None:
    lines = conn.execute(select(inbound_order_lines).where(inbound_order_lines.c.order_id == order_id)).all()
    received = sum(x.received_qty for x in lines)
    status = "received" if all(x.received_qty >= x.qty for x in lines) else "partially_received" if received else "confirmed"
    conn.execute(update(inbound_orders).where(inbound_orders.c.id == order_id).values(status=status))
