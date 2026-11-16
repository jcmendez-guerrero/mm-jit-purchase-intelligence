"""T066 (forecast): explanations and backtest results are removed only once older than five years; the removal is audited and repeatable (FR-025)."""

from datetime import UTC, datetime

import pytest
from audit import RETENTION_PURGED, verify_chain
from db.tables import audit_events, backtest_jobs, forecast_explanations, forecast_runs, metadata, product_backtest
from runs.retention import cutoff, purge
from sqlalchemy import create_engine, func, insert, select
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
OLD = datetime(2021, 11, 15, 12, 0, tzinfo=UTC)
KEPT = datetime(2021, 11, 17, 12, 0, tzinfo=UTC)


@pytest.fixture
def conn():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    metadata.create_all(eng)
    with eng.begin() as c:
        yield c


def _run_with_explanation(conn, run_id, started_at):
    conn.execute(insert(forecast_runs).values(id=run_id, started_at=started_at, model_versions={}, input_hash=run_id, config={}, status="completed"))
    conn.execute(insert(forecast_explanations).values(
        run_id=run_id, variant_id=1, sku="EJ-1", model_version="m1", method="croston", method_reason_code="intermittent", provenance_mix={},
        confidence_reason_codes=[], eligibility="eligible", eligibility_reason_codes=[]))


def _backtest(conn, run_id, created_at):
    conn.execute(insert(product_backtest).values(backtest_run_id=run_id, variant_id=1, sku="EJ-1", periods=3, beats_baseline=True, model_version="m1", created_at=created_at))


def _job(conn, job_id, status, started_at):
    conn.execute(insert(backtest_jobs).values(id=job_id, scope="product", status=status, requested_by="buyer-1", started_at=started_at))


def _count(conn, table):
    return conn.execute(select(func.count()).select_from(table)).scalar()


def test_cutoff_is_five_years_back_and_handles_29_february():
    assert cutoff(NOW) == datetime(2021, 11, 16, 12, 0, tzinfo=UTC)
    assert cutoff(datetime(2028, 2, 29, tzinfo=UTC)) == datetime(2023, 2, 28, tzinfo=UTC)


def test_only_older_records_are_removed_and_runs_are_kept(conn):
    _run_with_explanation(conn, "old", OLD)
    _run_with_explanation(conn, "new", KEPT)
    _backtest(conn, "old", OLD)
    _backtest(conn, "new", KEPT)
    _job(conn, "j-old", "completed", OLD)
    _job(conn, "j-new", "completed", KEPT)
    assert purge(conn, now=NOW) == {"forecast_explanations": 1, "product_backtest": 1, "backtest_jobs": 1}
    assert _count(conn, forecast_runs) == 2          # runs themselves are never part of this job
    assert conn.execute(select(forecast_explanations.c.run_id)).scalar() == "new"


def test_a_running_job_is_never_removed(conn):
    _job(conn, "j-running", "running", OLD)
    assert purge(conn, now=NOW)["backtest_jobs"] == 0


def test_the_removal_is_audited_and_repeatable(conn):
    _backtest(conn, "old", OLD)
    purge(conn, now=NOW)
    row = conn.execute(select(audit_events).where(audit_events.c.action == RETENTION_PURGED)).one()
    assert row.after["product_backtest"] == 1
    assert verify_chain(conn).ok
    assert purge(conn, now=NOW) == {"forecast_explanations": 0, "product_backtest": 0, "backtest_jobs": 0}


def test_a_pass_that_removes_nothing_writes_no_audit_event(conn):
    _backtest(conn, "new", KEPT)
    assert purge(conn, now=NOW) == {"forecast_explanations": 0, "product_backtest": 0, "backtest_jobs": 0}
    assert conn.execute(select(func.count()).select_from(audit_events)).scalar() == 0
