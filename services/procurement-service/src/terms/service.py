"""T080: supplier order terms, versioned and buyer-maintained."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from audit.chain import append as audit
from db.tables import supplier_terms, suppliers
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection, Row


class TermsError(Exception):
    pass


@dataclass(frozen=True)
class Terms:
    min_order_value: Decimal | None = None
    min_qty_for_delivery: int | None = None
    free_delivery_threshold: Decimal | None = None
    delivery_charge: Decimal | None = None
    order_days: tuple[int, ...] = ()
    delivery_schedule: str | None = None


def validate(t: Terms) -> None:
    for name in ("min_order_value", "free_delivery_threshold", "delivery_charge"):
        v = getattr(t, name)
        if v is not None and v < 0:
            raise TermsError(f"{name} must not be negative")
    if t.min_qty_for_delivery is not None and t.min_qty_for_delivery < 0:
        raise TermsError("min_qty_for_delivery must not be negative")
    if len(set(t.order_days)) != len(t.order_days) or any(not 1 <= d <= 7 for d in t.order_days):
        raise TermsError("order_days must be unique ISO weekdays 1..7")
    if t.delivery_schedule is not None and len(t.delivery_schedule) > 200:
        raise TermsError("delivery_schedule is too long")
    if (t.free_delivery_threshold is not None and t.min_order_value is not None and t.free_delivery_threshold < t.min_order_value):
        raise TermsError("free_delivery_threshold cannot be below min_order_value")


def save_terms(conn: Connection, supplier_id: str, terms: Terms, actor: str, now: datetime | None = None) -> int:
    """Appends a new version; earlier versions are kept. Returns the new version number."""
    validate(terms)
    if conn.execute(select(suppliers.c.id).where(suppliers.c.id == supplier_id)).first() is None:
        raise TermsError("unknown supplier")
    now = now or datetime.now(UTC)
    before = current_terms(conn, supplier_id)
    conn.execute(insert(supplier_terms).values(
        supplier_id=supplier_id, min_order_value=terms.min_order_value, min_qty_for_delivery=terms.min_qty_for_delivery,
        free_delivery_threshold=terms.free_delivery_threshold, delivery_charge=terms.delivery_charge, order_days=list(terms.order_days),
        delivery_schedule=terms.delivery_schedule, valid_from=now, changed_by=actor))
    n = len(versions(conn, supplier_id))
    audit(conn, actor, "terms.saved", "supplier_terms", supplier_id, before=_dump(before) if before else None, after=_dump(terms), now=now)
    return n


def _dump(t: Terms | Row[Any]) -> dict[str, Any]:
    return {"min_order_value": str(t.min_order_value) if t.min_order_value is not None else None, "min_qty_for_delivery": t.min_qty_for_delivery,
            "free_delivery_threshold": str(t.free_delivery_threshold) if t.free_delivery_threshold is not None else None,
            "delivery_charge": str(t.delivery_charge) if t.delivery_charge is not None else None,
            "order_days": list(t.order_days), "delivery_schedule": t.delivery_schedule}


def versions(conn: Connection, supplier_id: str) -> list[Row[Any]]:
    return list(conn.execute(select(supplier_terms).where(supplier_terms.c.supplier_id == supplier_id)
                             .order_by(supplier_terms.c.valid_from, supplier_terms.c.id)).all())


def current_terms(conn: Connection, supplier_id: str, as_of: datetime | None = None) -> Terms | None:
    as_of = as_of or datetime.now(UTC)
    chosen = None
    for r in versions(conn, supplier_id):
        valid = r.valid_from if r.valid_from.tzinfo else r.valid_from.replace(tzinfo=UTC)
        if valid <= as_of:
            chosen = r
    if chosen is None:
        return None
    dec = lambda v: None if v is None else Decimal(str(v))  # noqa: E731
    return Terms(dec(chosen.min_order_value), chosen.min_qty_for_delivery, dec(chosen.free_delivery_threshold), dec(chosen.delivery_charge),
                 tuple(chosen.order_days), chosen.delivery_schedule)
