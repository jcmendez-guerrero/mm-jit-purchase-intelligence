"""Queue dispatch by event type: routing, dedup, poison and retry behaviour."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from mmi_common.bus import POISON_SUFFIX, InMemoryBus, new_envelope
from mmi_common.busfactory import bus_from_env
from mmi_common.dispatch import RejectMessageError, consume_queue
from mmi_common.outbox import inbox_table
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, event, insert, select

CID = "7d3b7c3e-1c0e-4f6a-9d58-0c7a1a2b3c4d"


class Blobs:
    def __init__(self):
        self.store = {}

    def get(self, uri):
        return self.store[uri]


@pytest.fixture
def env():
    md = MetaData()
    inbox = inbox_table(md)
    seen = Table("seen", md, Column("n", Integer, primary_key=True, autoincrement=True), Column("kind", String(40)))
    eng = create_engine("sqlite://")

    @event.listens_for(eng, "connect")
    def _c(c, _):
        c.isolation_level = None

    @event.listens_for(eng, "begin")
    def _b(conn):
        conn.exec_driver_sql("BEGIN")

    md.create_all(eng)
    return eng, inbox, seen, InMemoryBus(), Blobs()


def send(bus, blobs, type_, body=None, age=timedelta(0), tamper=False, rid="r1"):
    data = json.dumps(body or {"x": 1}).encode()
    uri = f"mem://{type_}/{rid}/{len(blobs.store)}"
    blobs.store[uri] = data + (b" " if tamper else b"")
    env = new_envelope(type_, rid, data, uri, CID, occurred_at=datetime.now(UTC) - age)
    bus.send("q", env)
    return env


def handlers(seen, calls):
    def a(conn, env, payload):
        calls.append(("a", json.loads(payload)))
        conn.execute(insert(seen).values(kind="a"))

    def b(conn, env, payload):
        conn.execute(insert(seen).values(kind="b"))
        raise RejectMessageError

    return {"inventory.demand.updated.v1": a, "inventory.snapshot.created.v1": b}


def test_one_queue_routes_several_event_types_to_their_handlers(env):
    eng, inbox, seen, bus, blobs = env
    calls = []
    send(bus, blobs, "inventory.demand.updated.v1", {"v": 7})
    stats = consume_queue(eng, bus, blobs, "q", inbox, handlers(seen, calls))
    assert (stats.applied, stats.rejected) == (1, 0) and calls == [("a", {"v": 7})] and bus.depth("q") == 0


def test_duplicate_events_are_acknowledged_without_effect(env):
    eng, inbox, seen, bus, blobs = env
    e = send(bus, blobs, "inventory.demand.updated.v1")
    consume_queue(eng, bus, blobs, "q", inbox, handlers(seen, []))
    bus.send("q", e)
    stats = consume_queue(eng, bus, blobs, "q", inbox, handlers(seen, []))
    assert stats.duplicates == 1 and stats.applied == 0
    with eng.connect() as c:
        assert len(c.execute(select(seen)).all()) == 1


def test_unknown_stale_tampered_and_rejected_messages_are_poisoned(env):
    eng, inbox, seen, bus, blobs = env
    send(bus, blobs, "forecast.completed.v1", {"run_id": "x", "input_hash": "h", "eligible_count": 1}, rid="unknown-type")
    send(bus, blobs, "inventory.demand.updated.v1", age=timedelta(hours=48), rid="stale")
    send(bus, blobs, "inventory.demand.updated.v1", tamper=True, rid="tampered")
    send(bus, blobs, "inventory.snapshot.created.v1", rid="handler-rejects")
    stats = consume_queue(eng, bus, blobs, "q", inbox, handlers(seen, []))
    assert stats.rejected == 4 and stats.applied == 0 and bus.depth("q") == 0 and bus.depth("q" + POISON_SUFFIX) == 4
    with eng.connect() as c:
        assert c.execute(select(seen)).all() == [] and c.execute(select(inbox)).all() == []      # the rejecting handler's work was rolled back


def test_a_failing_handler_rolls_back_and_leaves_the_message_for_retry(env):
    eng, inbox, seen, bus, blobs = env

    def boom(conn, env_, payload):
        conn.execute(insert(seen).values(kind="partial"))
        raise RuntimeError("db hiccup")

    send(bus, blobs, "inventory.demand.updated.v1")
    stats = consume_queue(eng, bus, blobs, "q", inbox, {"inventory.demand.updated.v1": boom})
    assert stats.failed == 1 and bus.depth("q") == 1
    with eng.connect() as c:
        assert c.execute(select(seen)).all() == [] and c.execute(select(inbox)).all() == []
    stats = consume_queue(eng, bus, blobs, "q", inbox, handlers(seen, []))
    assert stats.applied == 1


def test_bus_needs_configuration(monkeypatch):
    monkeypatch.delenv("MMI_QUEUE_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("MMI_QUEUE_CONNECTION", raising=False)
    monkeypatch.delenv("MMI_QUEUE_URL", raising=False)
    with pytest.raises(RuntimeError):
        bus_from_env()
