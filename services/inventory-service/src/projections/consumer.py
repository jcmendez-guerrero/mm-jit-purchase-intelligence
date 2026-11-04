"""T044: inbox consumer for siweb.sync.completed.v1.

Validation (schema, freshness, checksum) happens before anything is applied. Duplicates are acknowledged
without effect. A failing handler rolls back its inbox registration and the message is retried, then poisoned.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from db.tables import inbox
from mmi_common.bus import MessageBus, MessageRejected, validate_envelope, verify_payload
from mmi_common.outbox import register_once
from mmi_common.time import ASSUMED_LOCAL_TZ
from sqlalchemy.engine import Engine

from projections.apply import TOMBSTONE_AFTER_DEFAULT, apply_payload
from projections.blob import BlobReader

log = logging.getLogger("inventory.consumer")
QUEUE = "inventory-sync-completed"
EVENT_TYPE = "siweb.sync.completed.v1"


@dataclass
class Stats:
    applied: int = 0
    duplicates: int = 0
    rejected: int = 0
    failed: int = 0


def consume_once(engine: Engine, bus: MessageBus, blobs: BlobReader, queue: str = QUEUE, batch: int = 10,
                 tombstone_after: int = TOMBSTONE_AFTER_DEFAULT, now: datetime | None = None) -> Stats:
    stats = Stats()
    for msg in bus.receive(queue, batch):
        env = msg.body
        try:
            validate_envelope(env, now=now)
            if env["type"] != EVENT_TYPE:
                raise MessageRejected(f"unexpected event type {env['type']}")
            payload = blobs.get(env["payload_ref"]["uri"])
            verify_payload(env, payload)
            doc = json.loads(payload)
        except (MessageRejected, ValueError, OSError, KeyError) as exc:
            log.error("rejected message: %s", type(exc).__name__)
            bus.poison(queue, msg.receipt)
            stats.rejected += 1
            continue
        try:
            occurred = datetime.fromisoformat(env["occurred_at"].replace("Z", "+00:00"))
            day = occurred.astimezone(ZoneInfo(ASSUMED_LOCAL_TZ)).date()
            with engine.begin() as conn:
                if not register_once(conn, inbox, env["event_id"], env["type"]):
                    stats.duplicates += 1
                else:
                    apply_payload(conn, doc, day, tombstone_after)
                    stats.applied += 1
            bus.complete(queue, msg.receipt)
        except Exception:
            log.exception("handler failed; message will be retried")
            bus.abandon(queue, msg.receipt)
            stats.failed += 1
    return stats


__all__ = ["QUEUE", "UTC", "Stats", "consume_once"]
