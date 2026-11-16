"""T066 (inventory): quality records are removed only once older than five years; the removal is audited and repeatable (FR-025)."""

from datetime import UTC, date, datetime

import pytest
from audit import RETENTION_PURGED, verify_chain
from db.tables import anomaly_flags, audit_events, data_quality_snapshot, metadata
from quality.retention import cutoff, purge
from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
OLD = datetime(2021, 11, 15, 12, 0, tzinfo=UTC)       # just over five years
KEPT = datetime(2021, 11, 17, 12, 0, tzinfo=UTC)      # just under five years


@pytest.fixture
def conn():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    metadata.create_all(eng)
    with eng.begin() as c:
        yield c


def _snapshot(conn, variant, built_at):
    conn.execute(insert(data_quality_snapshot).values(
        variant_id=variant, period_start=date(2021, 1, 1), period_end=date(2021, 3, 31), days_in_period=90, days_with_data=80, coverage_ratio="0.888889",
        gap_days=[], reason_counts={}, excluded_by_type={}, origin="erp", config_version_id="c1", input_hash=f"h{variant}", built_at=built_at))


def _flag(conn, variant, created_at):
    conn.execute(insert(anomaly_flags).values(variant_id=variant, day=date(2021, 2, 1), rule_id="mad_outlier", original_value="90.0000", decision="accepted", created_at=created_at))


def _count(conn, table):
    return conn.execute(select(func.count()).select_from(table)).scalar()


def test_cutoff_is_five_years_back_and_handles_29_february():
    assert cutoff(NOW) == datetime(2021, 11, 16, 12, 0, tzinfo=UTC)
    assert cutoff(datetime(2028, 2, 29, tzinfo=UTC)) == datetime(2023, 2, 28, tzinfo=UTC)


def test_nothing_is_removed_before_five_years_and_older_rows_are_removed(conn):
    _snapshot(conn, 1, OLD)
    _snapshot(conn, 2, KEPT)
    _flag(conn, 1, OLD)
    _flag(conn, 2, KEPT)
    assert purge(conn, now=NOW) == {"data_quality_snapshot": 1, "anomaly_flags": 1}
    assert _count(conn, data_quality_snapshot) == 1 and _count(conn, anomaly_flags) == 1
    assert conn.execute(select(data_quality_snapshot.c.variant_id)).scalar() == 2


def test_the_removal_is_audited_with_counts_and_the_chain_stays_valid(conn):
    _snapshot(conn, 1, OLD)
    purge(conn, now=NOW)
    row = conn.execute(select(audit_events).where(audit_events.c.action == RETENTION_PURGED)).one()
    assert row.after["data_quality_snapshot"] == 1 and row.after["anomaly_flags"] == 0
    assert verify_chain(conn).ok


def test_running_again_removes_nothing_more(conn):
    _snapshot(conn, 1, OLD)
    purge(conn, now=NOW)
    assert purge(conn, now=NOW) == {"data_quality_snapshot": 0, "anomaly_flags": 0}
