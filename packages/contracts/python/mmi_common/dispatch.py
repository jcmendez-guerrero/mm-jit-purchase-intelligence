"""Queue consumption by event type, shared by every service.

One queue per consumer service carries several event types (infra/bicep: inventory-in, forecast-in, procurement-in...).
For each message: validate the envelope (schema, freshness), load the payload and verify its checksum, then run the
handler for its type inside one database transaction together with the inbox registration. Duplicates are acknowledged
without effect, permanently bad messages go to the poison queue, and a failing handler rolls back and is retried.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import Table
from sqlalchemy.engine import Connection, Engine

from .bus import MessageBus, MessageRejected, validate_envelope, verify_payload
from .outbox import register_once

log = logging.getLogger("mmi.dispatch")

Handler = Callable[[Connection, dict[str, Any], bytes], None]


class BlobReader(Protocol):
    def get(self, uri: str) -> bytes: ...


class RejectMessageError(Exception):
    """Raised by a handler for a message that can never succeed (it goes to the poison queue, not a retry)."""


@dataclass
class DispatchStats:
    applied: int = 0
    duplicates: int = 0
    rejected: int = 0
    failed: int = 0


def consume_queue(engine: Engine, bus: MessageBus, blobs: BlobReader, queue: str, inbox: Table, handlers: Mapping[str, Handler],
                  now: datetime | None = None, batch: int = 10) -> DispatchStats:
    stats = DispatchStats()
    for msg in bus.receive(queue, batch):
        env = msg.body
        try:
            validate_envelope(env, now=now)
            handler = handlers.get(env["type"])
            if handler is None:
                raise MessageRejected(f"no handler for {env['type']}")
            payload = blobs.get(env["payload_ref"]["uri"])
            verify_payload(env, payload)
        except (MessageRejected, ValueError, OSError, KeyError) as exc:
            log.error("POISON_MESSAGE %s", type(exc).__name__)
            bus.poison(queue, msg.receipt)
            stats.rejected += 1
            continue
        try:
            with engine.begin() as conn:
                if register_once(conn, inbox, env["event_id"], env["type"]):
                    handler(conn, env, payload)
                    stats.applied += 1
                else:
                    stats.duplicates += 1
            bus.complete(queue, msg.receipt)
        except RejectMessageError:
            log.error("POISON_MESSAGE handler rejected %s", env["type"])
            bus.poison(queue, msg.receipt)
            stats.rejected += 1
        except Exception:
            log.exception("handler failed for %s; message will be retried", env["type"])
            bus.abandon(queue, msg.receipt)
            stats.failed += 1
    return stats
