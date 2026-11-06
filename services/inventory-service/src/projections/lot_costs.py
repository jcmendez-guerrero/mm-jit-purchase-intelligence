"""T127: projection of lot acquisition costs from procurement.lot_cost.changed.v1 (read-only copy; no cross-service SQL)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from db.tables import lot_cost_projection
from mmi_common.dispatch import RejectMessageError
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

SOURCES = ("confirmed_order", "receipt_correction", "buyer_entry")


def apply_lot_cost(conn: Connection, doc: dict[str, Any], at: datetime) -> None:
    """Upsert one (variant, supplier, lot). An older event never overwrites a newer one (redelivery and reordering are safe)."""
    try:
        variant, supplier, lot = int(doc["variant_id"]), str(doc["supplier_id"]), str(doc["lot"])
        cost = Decimal(str(doc["unit_cost"]))
        source = str(doc["source"])
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise RejectMessageError from exc
    if not cost.is_finite() or cost < 0 or source not in SOURCES or not lot:
        raise RejectMessageError
    key = (lot_cost_projection.c.variant_id == variant) & (lot_cost_projection.c.supplier_id == supplier) & (lot_cost_projection.c.lot == lot)
    cur = conn.execute(select(lot_cost_projection.c.updated_at).where(key)).first()
    if cur is None:
        conn.execute(insert(lot_cost_projection).values(variant_id=variant, supplier_id=supplier, lot=lot, unit_cost=cost, source=source, updated_at=at))
    elif _aware(cur.updated_at) <= at:
        conn.execute(update(lot_cost_projection).where(key).values(unit_cost=cost, source=source, updated_at=at))


def _aware(dt: datetime) -> datetime:
    from datetime import UTC

    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
