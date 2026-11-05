"""T136: delete raw payloads past ``expires_at`` (default retention 90 days, set when written)."""

from __future__ import annotations

from datetime import UTC, datetime

from db.tables import raw_payload_index
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from storage.blob import BlobStore


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def purge_expired(engine: Engine, store: BlobStore, now: datetime) -> int:
    """Remove expired blobs and their index rows; unexpired payloads are untouched. Returns the number purged."""
    purged = 0
    with engine.begin() as conn:
        for row in conn.execute(select(raw_payload_index)).all():
            if _aware(row.expires_at) <= now:
                store.delete(row.blob_uri)  # idempotent: a blob already gone does not block the index cleanup
                conn.execute(delete(raw_payload_index).where(raw_payload_index.c.blob_uri == row.blob_uri))
                purged += 1
    return purged
