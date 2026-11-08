"""T022: seed activations, rollbacks and parameter changes are hash-chained and tamper-evident."""

from datetime import UTC, datetime

import pytest
from audit import GENESIS, append, verify_chain
from db.tables import audit_events, metadata
from sqlalchemy import create_engine, delete, update
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


@pytest.fixture
def conn():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    metadata.create_all(eng)
    with eng.begin() as c:
        yield c


def test_chain_links_and_verifies(conn):
    h1 = append(conn, "buyer-1", "seed.activated", "seed_datasets", "d1", before=None, after={"version": 1}, now=NOW)
    append(conn, "buyer-1", "seed.rolled_back", "seed_datasets", "d1", before={"version": 1}, after=None, now=NOW)
    rows = conn.execute(audit_events.select().order_by(audit_events.c.id)).all()
    assert rows[0].prev_hash == GENESIS and rows[1].prev_hash == h1
    assert verify_chain(conn).ok


def test_tampering_and_removal_are_detected(conn):
    for i in range(3):
        append(conn, "a", "seed.activated", "seed_datasets", f"d{i}", after={"version": i}, now=NOW)
    conn.execute(update(audit_events).where(audit_events.c.entity_id == "d2").values(actor="someone-else"))
    assert verify_chain(conn).reason == "content altered"
    conn.execute(delete(audit_events).where(audit_events.c.entity_id == "d1"))
    assert not verify_chain(conn).ok
