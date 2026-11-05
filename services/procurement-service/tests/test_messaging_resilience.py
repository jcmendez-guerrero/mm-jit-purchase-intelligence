"""T120: Integration tests for messaging resilience: replay, duplicate, forged messages, and poison queue handling."""

import json
import uuid

import pytest
from db.tables import inbox, metadata
from mmi_common.bus import (
    InMemoryBus,
    MessageRejected,
    new_envelope,
    verify_payload,
)
from mmi_common.outbox import register_once
from sqlalchemy import create_engine, select


@pytest.fixture
def test_engine():
    eng = create_engine("sqlite:///:memory:")
    metadata.create_all(eng)
    return eng


def test_inbox_deduplication_ignores_replayed_and_duplicate_messages(test_engine):
    event_id = str(uuid.uuid4())
    event_type = "procurement.order.confirmed.v1"

    with test_engine.begin() as conn:
        first_time = register_once(conn, inbox, event_id, event_type)
        assert first_time is True, "First occurrence should be accepted and registered"

    with test_engine.begin() as conn:
        second_time = register_once(conn, inbox, event_id, event_type)
        assert second_time is False, "Replay/duplicate must be detected and rejected"

    with test_engine.begin() as conn:
        count = conn.execute(select(inbox).where(inbox.c.event_id == event_id)).all()
        assert len(count) == 1, "Inbox must contain exactly one record"


def test_forged_envelope_tamper_detection():
    run_id = str(uuid.uuid4())
    original_payload = json.dumps({"order_id": "ord-1", "amount": "100.00"}).encode("utf-8")
    env = new_envelope("procurement.order.confirmed.v1", run_id, original_payload, "uri://test", "corr-1")

    # Valid payload passes verification without exception
    verify_payload(env, original_payload)

    # Tampered payload raises MessageRejected
    tampered_payload = json.dumps({"order_id": "ord-1", "amount": "999999.00"}).encode("utf-8")
    with pytest.raises(MessageRejected):
        verify_payload(env, tampered_payload)


def test_poison_message_diverted_to_poison_queue():
    bus = InMemoryBus()
    queue_name = "procurement-events"

    # Send a message to the queue
    env = new_envelope("procurement.order.confirmed.v1", "res-1", b"{}", "uri://test", "corr-1")
    bus.send(queue_name, env)

    received = bus.receive(queue_name)
    assert len(received) == 1
    msg = received[0]

    # Consumer rejects message (e.g. malformed or poisoned) and routes to poison queue
    bus.poison(queue_name, msg.receipt)

    # Message is no longer in main queue
    assert len(bus.receive(queue_name)) == 0

    # Message is in the poison queue
    poison_msgs = bus.receive(f"{queue_name}-poison")
    assert len(poison_msgs) == 1
    assert poison_msgs[0].body["event_id"] == env["event_id"]
