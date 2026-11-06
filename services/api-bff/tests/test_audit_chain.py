"""T022: role changes are hash-chained and tamper-evident (same design as procurement-service)."""

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


def test_empty_chain_is_valid(conn):
    assert verify_chain(conn).ok


def test_append_links_each_event_to_the_previous(conn):
    h1 = append(conn, "admin-1", "roles.changed", "user_roles", "u1", before=["viewer"], after=["viewer", "buyer"], now=NOW)
    h2 = append(conn, "admin-1", "roles.changed", "user_roles", "u2", before=None, after=["approver"], now=NOW)
    rows = conn.execute(audit_events.select().order_by(audit_events.c.id)).all()
    assert rows[0].prev_hash == GENESIS and rows[1].prev_hash == h1 and rows[1].hash == h2
    assert verify_chain(conn).ok and verify_chain(conn).checked == 2


def test_altered_content_is_detected(conn):
    append(conn, "a", "roles.changed", "user_roles", "u1", after=["viewer"], now=NOW)
    append(conn, "a", "roles.changed", "user_roles", "u2", after=["buyer"], now=NOW)
    conn.execute(update(audit_events).where(audit_events.c.entity_id == "u1").values(after=["admin"]))
    check = verify_chain(conn)
    assert not check.ok and check.reason == "content altered"


def test_removed_event_is_detected(conn):
    for i in range(3):
        append(conn, "a", "roles.changed", "user_roles", f"u{i}", after=["viewer"], now=NOW)
    conn.execute(delete(audit_events).where(audit_events.c.entity_id == "u1"))
    check = verify_chain(conn)
    assert not check.ok and "removed or reordered" in (check.reason or "")
