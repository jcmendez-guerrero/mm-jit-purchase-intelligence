"""T054: quarantine exclusion and review release.

Quarantined movements stay out of demand and flows until a buyer decides. ``confirm`` releases a movement into
the series; ``ignore`` keeps it excluded and removes it from the open list. Decisions are audited and survive
re-syncs (a re-sent movement is never re-inserted, so the decision is not undone).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from db.tables import review_decisions, stock_movements
from mmi_common.time import utc_now
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

DECISIONS = ("confirm", "ignore")


class ReviewError(Exception):
    pass


@dataclass(frozen=True)
class ReviewItem:
    external_id: int
    variant_id: int
    reason: str
    quantity: int
    created_at_raw: str
    codes: list[str]


def list_open(conn: Connection) -> list[ReviewItem]:
    decided = select(review_decisions.c.external_id)
    rows = conn.execute(select(stock_movements).where(stock_movements.c.quarantined, stock_movements.c.external_id.not_in(decided))
                        .order_by(stock_movements.c.external_id)).all()
    return [ReviewItem(r.external_id, r.variant_id, r.reason, r.quantity, r.created_at_raw,
                       [c for c in (r.quarantine_codes or "").split(",") if c]) for r in rows]


def decide(conn: Connection, ids: Iterable[int], decision: str, by: str, now: datetime | None = None) -> int:
    """Record the decision for every id, all or nothing. Returns the number of movements decided."""
    if decision not in DECISIONS:
        raise ReviewError(f"decision must be one of {DECISIONS}")
    ids = list(dict.fromkeys(ids))
    open_ids = {i.external_id for i in list_open(conn)}
    unknown = [i for i in ids if i not in open_ids]
    if unknown:
        raise ReviewError(f"not in the open review list: {unknown}")
    if decision == "confirm":
        bad = conn.execute(select(stock_movements.c.external_id).where(
            stock_movements.c.external_id.in_(ids), stock_movements.c.created_at_utc.is_(None))).scalars().all()
        if bad:
            raise ReviewError(f"cannot confirm movements without a valid timestamp: {bad}")
    stamp = now or utc_now()
    for i in ids:
        conn.execute(insert(review_decisions).values(external_id=i, decision=decision, decided_by=by, decided_at=stamp))
    if decision == "confirm":
        conn.execute(update(stock_movements).where(stock_movements.c.external_id.in_(ids)).values(quarantined=False))
    return len(ids)
