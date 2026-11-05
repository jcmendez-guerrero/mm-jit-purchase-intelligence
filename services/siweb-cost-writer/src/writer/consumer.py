"""Queue consumer: validates the envelope, then lets the processor do (or refuse) the write."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from db.tables import inbox
from mmi_common.bus import MessageBus, MessageRejected, validate_envelope, verify_payload
from mmi_common.outbox import register_once
from sqlalchemy.engine import Engine

from writer.flow import ForgedRequestError, WriteProcessor

log = logging.getLogger("cost-writer")
QUEUE = "costwriter-in"
EVENT_TYPE = "procurement.cost.write_requested.v1"


class Blobs:
    def get(self, uri: str) -> bytes:
        from pathlib import Path

        return Path(uri.removeprefix("file://")).read_bytes()


def consume(engine: Engine, bus: MessageBus, blobs: Blobs, processor: WriteProcessor, queue: str = QUEUE, now: datetime | None = None) -> dict[str, int]:
    stats = {"processed": 0, "duplicates": 0, "rejected": 0, "forged": 0, "failed": 0}
    for msg in bus.receive(queue, 10):
        env = msg.body
        try:
            validate_envelope(env, now=now)   # also enforces the 1-hour freshness window of this event type
            if env["type"] != EVENT_TYPE:
                raise MessageRejected(f"unexpected event type {env['type']}")
            payload = blobs.get(env["payload_ref"]["uri"])
            verify_payload(env, payload)
            request_id = json.loads(payload)["cost_write_request_id"]
        except (MessageRejected, ValueError, OSError, KeyError):
            log.error("rejected message")
            bus.poison(queue, msg.receipt)
            stats["rejected"] += 1
            continue
        try:
            with engine.begin() as conn:
                first = register_once(conn, inbox, env["event_id"], env["type"])
            if not first:
                stats["duplicates"] += 1
            else:
                processor.process(request_id)
                stats["processed"] += 1
            bus.complete(queue, msg.receipt)
        except ForgedRequestError:
            log.error("FORGED_WRITE_REQUEST refused")
            bus.poison(queue, msg.receipt)       # poison queue + alert; no Siweb call was made
            stats["forged"] += 1
        except Exception:
            log.exception("write handler failed; will retry")
            bus.abandon(queue, msg.receipt)
            stats["failed"] += 1
    return stats
