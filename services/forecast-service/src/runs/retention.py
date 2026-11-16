"""T066: removing this feature's derived forecast records once they are five years old, never before (feature 012, FR-025).

Only ``forecast_explanations`` (aged by the start of their run), ``product_backtest`` and finished ``backtest_jobs`` are touched. Runs, forecast
values and every other table are left alone, and the removal is audited with its counts. Running it again removes nothing more.
"""

from __future__ import annotations

from datetime import UTC, datetime

from audit import RETENTION_PURGED
from audit import append as audit
from db.tables import backtest_jobs, forecast_explanations, forecast_runs, product_backtest
from sqlalchemy import delete, select
from sqlalchemy.engine import Connection

RETENTION_YEARS = 5


def cutoff(now: datetime, years: int = RETENTION_YEARS) -> datetime:
    try:
        return now.replace(year=now.year - years)
    except ValueError:                                              # 29 February: use the 28th
        return now.replace(year=now.year - years, day=28)


def purge(conn: Connection, now: datetime | None = None, years: int = RETENTION_YEARS) -> dict[str, int]:
    now = now or datetime.now(UTC)
    limit = cutoff(now, years)
    old_runs = select(forecast_runs.c.id).where(forecast_runs.c.started_at < limit)
    counts = {
        "forecast_explanations": conn.execute(delete(forecast_explanations).where(forecast_explanations.c.run_id.in_(old_runs))).rowcount,
        "product_backtest": conn.execute(delete(product_backtest).where(product_backtest.c.created_at < limit)).rowcount,
        "backtest_jobs": conn.execute(delete(backtest_jobs).where(backtest_jobs.c.status != "running", backtest_jobs.c.started_at < limit)).rowcount,
    }
    if any(counts.values()):                                        # a pass that removed nothing leaves no audit noise
        audit(conn, "retention-job", RETENTION_PURGED, "retention", limit.date().isoformat(), after={"before": limit.date().isoformat(), **counts}, now=now)
    return counts
