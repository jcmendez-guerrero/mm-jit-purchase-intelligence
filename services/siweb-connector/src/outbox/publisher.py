"""T042: publish siweb.sync.completed.v1 through the transactional outbox."""

from __future__ import annotations

from db.tables import outbox
from mmi_common.bus import new_envelope
from mmi_common.outbox import enqueue
from sqlalchemy.engine import Connection
from sync.raw_store import RawPayload

EVENT_TYPE = "siweb.sync.completed.v1"
SUBSCRIPTIONS = {EVENT_TYPE: ["inventory-sync-completed"]}


def publish_sync_completed(conn: Connection, run_id: str, raw: RawPayload, correlation_id: str) -> dict:
    """Insert in the caller's transaction so the event exists if and only if the run committed."""
    envelope = new_envelope(EVENT_TYPE, run_id, raw.data, raw.uri, correlation_id)
    enqueue(conn, outbox, envelope)
    return envelope
