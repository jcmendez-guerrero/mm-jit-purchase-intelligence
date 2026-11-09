"""MMI-6 (FR-014): retry-safe terms saves.

A client that sends an ``Idempotency-Key`` gets the original result back when it repeats the same request (for example after a lost
response), instead of a false revision conflict or a second version. The key is bound to a scope (supplier terms or product override),
a hash of the whole request (target, If-Match and body) and the version it created. The same key with different content is refused.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from db.tables import terms_idempotency
from sqlalchemy import delete, insert, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

__all__ = ["MAX_KEY_LENGTH", "RETENTION", "IdempotencyError", "forget_older_than", "remember", "replay", "request_hash", "validate_key"]

MAX_KEY_LENGTH = 120
RETENTION = timedelta(days=7)


class IdempotencyError(Exception):
    """A refusal with a stable code (see packages/contracts/errors/error_codes.json)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def validate_key(key: str) -> str:
    stripped = key.strip()
    if not stripped or len(stripped) > MAX_KEY_LENGTH or not stripped.isprintable():
        raise IdempotencyError("invalid_idempotency_key")
    return stripped


def request_hash(scope: str, target: str, if_match: str | None, body: dict[str, Any]) -> str:
    canonical = json.dumps({"scope": scope, "target": target, "if_match": if_match, "body": body}, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def replay(conn: Connection, scope: str, key: str, digest: str) -> int | None:
    """The version the first request created, or None when the key is new. The same key with other content is refused."""
    row = conn.execute(select(terms_idempotency).where(terms_idempotency.c.scope == scope, terms_idempotency.c.key == key)).first()
    if row is None:
        return None
    if row.request_hash != digest:
        raise IdempotencyError("idempotency_key_reuse")
    return int(row.result_version)


def remember(conn: Connection, scope: str, key: str, digest: str, version: int, actor: str, now: datetime | None = None) -> bool:
    """Stores the key after a successful save. False means a concurrent request with the same key won; the caller must roll back and retry."""
    try:
        with conn.begin_nested():
            conn.execute(insert(terms_idempotency).values(scope=scope, key=key, request_hash=digest, result_version=version, actor=actor,
                                                          created_at=now or datetime.now(UTC)))
    except IntegrityError:
        return False
    return True


def forget_older_than(conn: Connection, now: datetime | None = None, retention: timedelta = RETENTION) -> int:
    """Housekeeping for the worker: keys older than the retention period can no longer be replayed."""
    result = conn.execute(delete(terms_idempotency).where(terms_idempotency.c.created_at < (now or datetime.now(UTC)) - retention))
    return int(result.rowcount or 0)
