"""T011 (inventory): the quality audit actions fit the audit column and keep the hash chain valid."""

from datetime import UTC, datetime

import pytest
from audit import ANOMALY_DECIDED, CLASSES_RECOMPUTED, append, verify_chain
from db.tables import audit_events, metadata
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def conn():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    metadata.create_all(eng)
    with eng.begin() as c:
        yield c


def test_action_names_fit_the_column_and_use_the_quality_prefix():
    limit = audit_events.c.action.type.length
    for action in (ANOMALY_DECIDED, CLASSES_RECOMPUTED):
        assert action.startswith("quality.") and len(action) <= limit


def test_events_with_these_actions_chain_and_verify_without_free_text(conn):
    append(conn, "buyer-1", ANOMALY_DECIDED, "anomaly_flags", "7:2026-01-02",
           before={"decision": "pending"}, after={"decision": "excluded", "reason_code": "data_error", "versions": {"config": "c1"}}, now=NOW)
    append(conn, "buyer-1", CLASSES_RECOMPUTED, "product_segments", "run-1", after={"products": 12, "config": "c1"}, now=NOW)
    assert verify_chain(conn).ok
