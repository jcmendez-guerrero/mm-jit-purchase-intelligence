"""Hash-chained, append-only writer audit (who released, previous and new value, outcome). Own copy: no shared schema."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from db.tables import writer_audit
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

GENESIS = "0" * 64


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _body(ts: datetime, request_id: str, actor: str, action: str, product_id: int | None, contact: int | None, prev: Any, new: Any, detail: Any) -> dict[str, Any]:
    return {"ts": _aware(ts).isoformat(), "request_id": request_id, "actor_ref": actor, "action": action, "product_id": product_id,
            "supplier_contact_id": contact, "previous_cost_cents": prev, "new_cost_cents": new, "detail": detail}


def _hash(prev_hash: str, body: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)).encode()).hexdigest()


def record(conn: Connection, request_id: str, actor: str, action: str, product_id: int | None = None, contact: int | None = None,
           previous: int | None = None, new: int | None = None, detail: dict[str, Any] | None = None, now: datetime | None = None) -> str:
    ts = now or datetime.now(UTC)
    prev_s, new_s = (None if previous is None else str(previous)), (None if new is None else str(new))
    for attempt in range(3):
        tip = conn.execute(select(writer_audit.c.hash).order_by(writer_audit.c.id.desc()).limit(1)).scalar() or GENESIS
        digest = _hash(tip, _body(ts, request_id, actor, action, product_id, contact, prev_s, new_s, detail))
        try:
            with conn.begin_nested():
                conn.execute(insert(writer_audit).values(ts=ts, request_id=request_id, actor_ref=actor, action=action, product_id=product_id, supplier_contact_id=contact,
                                                         previous_cost_cents=prev_s, new_cost_cents=new_s, detail=detail, prev_hash=tip, hash=digest))
            return digest
        except IntegrityError:
            if attempt == 2:
                raise
    raise AssertionError("unreachable")


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    checked: int
    broken_at: int | None = None


def verify(conn: Connection) -> ChainCheck:
    prev, n = GENESIS, 0
    for r in conn.execute(select(writer_audit).order_by(writer_audit.c.id)).all():
        n += 1
        body = _body(r.ts, r.request_id, r.actor_ref, r.action, r.product_id, r.supplier_contact_id, r.previous_cost_cents, r.new_cost_cents, r.detail)
        if r.prev_hash != prev or _hash(prev, body) != r.hash:
            return ChainCheck(False, n, r.id)
        prev = r.hash
    return ChainCheck(True, n)
