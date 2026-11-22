"""T066: removing this feature's derived quality records once they are five years old, never before (feature 018, FR-025).

Only ``data_quality_snapshot`` and ``anomaly_flags`` are touched, only rows older than the retention period (a flag is as old as its latest decision), and a removal is audited with its counts.
ERP-derived data, demand, stock and every other table are never involved. Running it again removes nothing more.
"""

from __future__ import annotations

from datetime import UTC, datetime

from audit import RETENTION_PURGED
from audit import append as audit
from db.tables import anomaly_flags, data_quality_snapshot
from sqlalchemy import delete, func
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
    # a flag counts as recent while its decision is: a buyer's exclusion made in the last five years is never purged
    flags = conn.execute(delete(anomaly_flags).where(func.coalesce(anomaly_flags.c.decided_at, anomaly_flags.c.created_at) < limit)).rowcount
    counts = {"data_quality_snapshot": snapshots, "anomaly_flags": flags}
    if any(counts.values()):                                        # a pass that removed nothing leaves no audit noise
        audit(conn, "retention-job", RETENTION_PURGED, "retention", limit.date().isoformat(), after={"before": limit.date().isoformat(), **counts}, now=now)
    return counts
