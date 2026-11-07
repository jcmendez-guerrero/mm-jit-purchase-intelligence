"""Hash-chained, append-only audit events for demand-rule changes (same design as procurement-service).

hash = sha256(prev_hash || canonical JSON of the event body). The UNIQUE constraint on ``prev_hash`` means two writers
cannot both extend the same tip, so a concurrent append fails and is retried instead of forking the chain.
``verify_chain`` recomputes every link and reports the first event that was altered, removed or reordered.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from db.tables import audit_events
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

GENESIS = "0" * 64


def _canonical(body: dict[str, Any]) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str, body: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(body)).encode()).hexdigest()


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _body(ts: datetime, actor: str, action: str, entity: str, entity_id: str, before: Any, after: Any) -> dict[str, Any]:
    return {"ts": _aware(ts).isoformat(), "actor": actor, "action": action, "entity": entity, "entity_id": entity_id, "before": before, "after": after}


def append(conn: Connection, actor: str, action: str, entity: str, entity_id: str, before: Any = None, after: Any = None,
           now: datetime | None = None, retries: int = 3) -> str:
    ts = now or datetime.now(UTC)
    for attempt in range(retries):
        tip = conn.execute(select(audit_events.c.hash).order_by(audit_events.c.id.desc()).limit(1)).scalar()
        prev = tip or GENESIS
        digest = compute_hash(prev, _body(ts, actor, action, entity, entity_id, before, after))
        try:
            with conn.begin_nested():
                conn.execute(insert(audit_events).values(ts=ts, actor=actor, action=action, entity=entity, entity_id=entity_id,
                                                         before=before, after=after, prev_hash=prev, hash=digest))
            return digest
        except IntegrityError:
            if attempt == retries - 1:
                raise
    raise AssertionError("unreachable")


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    checked: int
    broken_at: int | None = None
    reason: str | None = None


def verify_chain(conn: Connection) -> ChainCheck:
    prev, n = GENESIS, 0
    for r in conn.execute(select(audit_events).order_by(audit_events.c.id)).all():
        n += 1
        if r.prev_hash != prev:
            return ChainCheck(False, n, r.id, "link broken: event removed or reordered")
        if compute_hash(prev, _body(r.ts, r.actor, r.action, r.entity, r.entity_id, r.before, r.after)) != r.hash:
            return ChainCheck(False, n, r.id, "content altered")
        prev = r.hash
    return ChainCheck(True, n)
