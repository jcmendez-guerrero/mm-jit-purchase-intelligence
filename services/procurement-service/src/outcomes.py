"""Consumer for siweb.cost.write_completed.v1: records what the writer reported on the cost write request."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from costs.writes import WriteError, apply_outcome
from db.tables import inbox
from mmi_common.bus import MessageBus, MessageRejected, validate_envelope, verify_payload
from mmi_common.outbox import register_once
from sqlalchemy.engine import Engine

log = logging.getLogger("procurement.outcomes")
QUEUE = "procurement-in"
EVENT_TYPE = "siweb.cost.write_completed.v1"


class BlobReader:
    """Reads the payload referenced by an envelope (file:// locally, blob URL in Azure through a subclass)."""

    def get(self, uri: str) -> bytes:
        from pathlib import Path

        return Path(uri.removeprefix("file://")).read_bytes()


def consume_outcomes(engine: Engine, bus: MessageBus, blobs: BlobReader, queue: str = QUEUE, now: datetime | None = None) -> dict[str, int]:
    stats = {"applied": 0, "duplicates": 0, "rejected": 0, "failed": 0}
    for msg in bus.receive(queue, 10):
        env = msg.body
        if env.get("type") != EVENT_TYPE:
            bus.complete(queue, msg.receipt)       # other event types on this queue are handled elsewhere
            continue
        try:
            validate_envelope(env, now=now)
            payload = blobs.get(env["payload_ref"]["uri"])
            verify_payload(env, payload)
            doc = json.loads(payload)
        except (MessageRejected, ValueError, OSError, KeyError):
            bus.poison(queue, msg.receipt)
            stats["rejected"] += 1
            continue
        try:
            with engine.begin() as conn:
                if not register_once(conn, inbox, env["event_id"], env["type"]):
                    stats["duplicates"] += 1
                else:
                    apply_outcome(conn, doc["cost_write_request_id"], doc["outcome"], int(doc.get("attempts", 0)), doc.get("error"), now)
                    stats["applied"] += 1
            bus.complete(queue, msg.receipt)
        except WriteError:
            log.exception("outcome refused")
            bus.poison(queue, msg.receipt)
            stats["rejected"] += 1
        except Exception:
            log.exception("outcome handler failed; will retry")
            bus.abandon(queue, msg.receipt)
            stats["failed"] += 1
    return stats
