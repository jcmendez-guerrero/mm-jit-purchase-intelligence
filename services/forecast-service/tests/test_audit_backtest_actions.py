"""T011 (forecast): the backtest audit actions fit the audit column and keep the hash chain valid."""

from datetime import UTC, datetime

import pytest
from audit import BACKTEST_COMPLETED, BACKTEST_STARTED, append, verify_chain
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


def test_action_names_fit_the_column_and_use_the_forecast_prefix():
    limit = audit_events.c.action.type.length
    for action in (BACKTEST_STARTED, BACKTEST_COMPLETED):
        assert action.startswith("forecast.") and len(action) <= limit


def test_events_with_these_actions_chain_and_verify(conn):
    append(conn, "buyer-1", BACKTEST_STARTED, "product_backtest", "b1", after={"scope": "catalogue", "config": "c1"}, now=NOW)
    append(conn, "buyer-1", BACKTEST_COMPLETED, "product_backtest", "b1", after={"products": 12}, now=NOW)
    assert verify_chain(conn).ok
