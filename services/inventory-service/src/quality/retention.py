"""T066: removing this feature's derived quality records once they are five years old, never before (feature 012, FR-025).

Only ``data_quality_snapshot`` and ``anomaly_flags`` are touched, only rows older than the retention period, and the removal is audited with its counts.
ERP-derived data, demand, stock and every other table are never involved. Running it again removes nothing more.
"""

from __future__ import annotations

from datetime import UTC, datetime

from audit import RETENTION_PURGED
from audit import append as audit
from db.tables import anomaly_flags, data_quality_snapshot
from sqlalchemy import delete
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
    snapshots = conn.execute(delete(data_quality_snapshot).where(data_quality_snapshot.c.built_at < limit)).rowcount
    flags = conn.execute(delete(anomaly_flags).where(anomaly_flags.c.created_at < limit)).rowcount
    counts = {"data_quality_snapshot": snapshots, "anomaly_flags": flags}
    audit(conn, "retention-job", RETENTION_PURGED, "retention", limit.date().isoformat(), after={"before": limit.date().isoformat(), **counts}, now=now)
    return counts
