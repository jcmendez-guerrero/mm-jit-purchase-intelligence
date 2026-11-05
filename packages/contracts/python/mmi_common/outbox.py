"""Transactional outbox relay (one message per subscribed queue) and inbox deduplication.

Services call ``outbox_table(metadata)`` / ``inbox_table(metadata)`` in their own schema,
insert outbox rows in the same transaction as their state change, and run ``relay_once``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from .bus import MessageBus
from .time import utc_now


def outbox_table(metadata: MetaData) -> Table:
    return Table(
        "outbox",
        metadata,
        Column("event_id", String(36), primary_key=True),
        Column("type", String(120), nullable=False),
        Column("envelope", JSON, nullable=False),
        Column("status", String(12), nullable=False, default="pending"),  # pending/sent
        Column("attempts", Integer, nullable=False, default=0),
        Column("created_at", DateTime(timezone=True), nullable=False, default=utc_now),
        Column("sent_at", DateTime(timezone=True)),
    )


def inbox_table(metadata: MetaData) -> Table:
    return Table(
        "inbox",
        metadata,
        Column("event_id", String(36), primary_key=True),
        Column("type", String(120), nullable=False),
        Column("processed_at", DateTime(timezone=True), nullable=False, default=utc_now),
    )


def enqueue(conn: Connection, outbox: Table, envelope: Mapping[str, object]) -> None:
    """Insert in the caller's transaction."""
    conn.execute(
        insert(outbox).values(
            event_id=envelope["event_id"], type=envelope["type"], envelope=dict(envelope),
            status="pending", attempts=0, created_at=utc_now(),
        )
    )


def relay_once(
    conn: Connection,
    outbox: Table,
    bus: MessageBus,
    subscriptions: Mapping[str, Sequence[str]],
    batch: int = 100,
) -> int:
    """Send pending events to every subscribed queue; returns the number marked sent.

    At-least-once: a crash between send and mark re-sends, and consumers deduplicate.
    Events with no subscriber are marked sent so they do not block the relay.
    """
    rows = conn.execute(
        select(outbox).where(outbox.c.status == "pending").order_by(outbox.c.created_at).limit(batch)
    ).all()
    sent = 0
    for row in rows:
        try:
            for queue in subscriptions.get(row.type, ()):
                bus.send(queue, row.envelope if isinstance(row.envelope, dict) else json.loads(row.envelope))
        except Exception:
            conn.execute(update(outbox).where(outbox.c.event_id == row.event_id).values(attempts=outbox.c.attempts + 1))
            raise
        conn.execute(
            update(outbox).where(outbox.c.event_id == row.event_id).values(status="sent", sent_at=utc_now())
        )
        sent += 1
    return sent


def register_once(conn: Connection, inbox: Table, event_id: str, type_: str) -> bool:
    """Return True the first time an event_id is seen; False for duplicates.

    Call inside the consumer's transaction so a failed handler rolls the registration back.
    """
    try:
        with conn.begin_nested():
            conn.execute(insert(inbox).values(event_id=event_id, type=type_, processed_at=utc_now()))
    except IntegrityError:
        return False
    return True


__all__ = ["datetime", "enqueue", "inbox_table", "outbox_table", "register_once", "relay_once"]
