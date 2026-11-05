"""T153: the Storage Queue bus behaves like the in-memory bus against a real emulator (Azurite). Needs Docker and RUN_AZURITE=1."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from azurite_fixture import available, azurite
from mmi_common.bus import POISON_SUFFIX, StorageQueueBus, new_envelope, validate_envelope

pytestmark = pytest.mark.skipif(not available(), reason="needs Docker and RUN_AZURITE=1")


@pytest.fixture(scope="module")
def bus():
    from azure.storage.queue import QueueServiceClient

    with azurite() as conn:
        yield StorageQueueBus(QueueServiceClient.from_connection_string(conn), max_deliveries=3, visibility_timeout=2)


def env():
    return new_envelope("forecast.completed.v1", str(uuid.uuid4()), b"{}", "file:///x", str(uuid.uuid4()))


def test_send_receive_complete_roundtrip_keeps_the_envelope_intact(bus):
    e = env()
    bus.send("queue-roundtrip", e)
    got = bus.receive("queue-roundtrip", 1)
    assert len(got) == 1 and got[0].body == e and got[0].delivery_count == 1
    validate_envelope(got[0].body, now=datetime.now(UTC))
    bus.complete("queue-roundtrip", got[0].receipt)
    assert bus.receive("queue-roundtrip", 1) == []


def test_an_abandoned_message_reappears_after_the_visibility_timeout_with_a_higher_count(bus):
    import time

    bus.send("queue-retry", env())
    first = bus.receive("queue-retry", 1)[0]
    bus.abandon("queue-retry", first.receipt)
    assert bus.receive("queue-retry", 1) == []                      # still invisible
    time.sleep(2.5)
    again = bus.receive("queue-retry", 1)
    assert len(again) == 1 and again[0].delivery_count == 2


def test_poison_moves_the_message_to_the_poison_queue(bus):
    e = env()
    bus.send("queue-poison", e)
    m = bus.receive("queue-poison", 1)[0]
    bus.poison("queue-poison", m.receipt)
    assert bus.receive("queue-poison", 1) == []
    p = bus.receive("queue-poison" + POISON_SUFFIX, 1)
    assert len(p) == 1 and p[0].body == e


def test_a_message_that_keeps_failing_is_poisoned_after_the_delivery_limit(bus):
    import time

    bus.send("queue-limit", env())
    for _ in range(3):
        m = bus.receive("queue-limit", 1)
        assert len(m) == 1
        bus.abandon("queue-limit", m[0].receipt)
        time.sleep(2.2)
    assert bus.receive("queue-limit", 1) == []
    assert len(bus.receive("queue-limit" + POISON_SUFFIX, 5)) == 1


def test_stale_envelopes_are_still_rejected_by_validation_not_by_the_transport(bus):
    old = new_envelope("forecast.completed.v1", "r", b"{}", "file:///x", str(uuid.uuid4()), occurred_at=datetime.now(UTC) - timedelta(days=3))
    bus.send("queue-stale", old)
    got = bus.receive("queue-stale", 1)[0]
    assert json.loads(json.dumps(got.body)) == old
    with pytest.raises(Exception, match="freshness"):
        validate_envelope(got.body, now=datetime.now(UTC))
