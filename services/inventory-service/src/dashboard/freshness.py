"""T011 (FR-003, FR-018, audit A16): per-source refresh time, origin and state, with one server-side stale threshold.

States: ``ok``, ``stale`` (older than the threshold), ``no_data`` (nothing loaded yet). ``error`` is set by the caller when a source cannot be read.
Origin is ``erp_sync`` for everything the sync collects; the local loader's data is not tagged in the source tables yet (audit A25), so ``local_load`` is only
reported once the aggregates carry that origin.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from db.tables import agg_daily_kpis, demand_observations, stock_lots, stock_movements, stock_snapshots
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

DEFAULT_STALE_AFTER_HOURS = 48          # same two days the web app used as a constant


def stale_after_hours() -> int:
    raw = os.environ.get("DASHBOARD_STALE_AFTER_HOURS", "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_STALE_AFTER_HOURS


@dataclass(frozen=True)
class Freshness:
    source: str
    refreshed_at: datetime | None
    origin: str
    state: str
    stale_after_hours: int
    original: str | None = None           # the timestamp text exactly as the source gave it, when the source keeps it

    def as_json(self) -> dict[str, object]:
        at = self.refreshed_at
        return {"source": self.source, "refreshed_at": at.isoformat() if at else None, "refreshed_at_original": self.original,
                "origin": self.origin, "state": self.state, "stale_after_hours": self.stale_after_hours}


def classify(refreshed_at: datetime | None, now: datetime, hours: int) -> str:
    if refreshed_at is None:
        return "no_data"
    if refreshed_at.tzinfo is None:
        refreshed_at = refreshed_at.replace(tzinfo=UTC)
    return "stale" if (now - refreshed_at).total_seconds() > hours * 3600 else "ok"


def _midnight(d: date | None) -> datetime | None:
    return None if d is None else datetime.combine(d, time.min, tzinfo=UTC)


def inventory_freshness(conn: Connection, now: datetime | None = None, hours: int | None = None) -> list[Freshness]:
    now, hours = now or datetime.now(UTC), hours or stale_after_hours()
    latest = conn.execute(select(agg_daily_kpis.c.refreshed_at, agg_daily_kpis.c.origin).order_by(agg_daily_kpis.c.refreshed_at.desc()).limit(1)).first()
    snap = conn.execute(select(func.max(stock_lots.c.seen_at))).scalar()          # when the stock was really collected
    if snap is None:                                                              # no lots: fall back to the snapshot day (measured from midnight UTC)
        snap = _midnight(conn.execute(select(func.max(stock_snapshots.c.snapshot_date))).scalar())
    mv = conn.execute(select(stock_movements.c.created_at_utc, stock_movements.c.created_at_raw).where(stock_movements.c.created_at_utc.is_not(None))
                      .order_by(stock_movements.c.created_at_utc.desc()).limit(1)).first()
    if mv is not None:
        moves, moves_raw = mv.created_at_utc, mv.created_at_raw                   # UTC value plus the original string (AGENTS rule 5)
    else:
        moves, moves_raw = _midnight(conn.execute(select(func.max(demand_observations.c.day))).scalar()), None
    out = [Freshness("inventory_snapshot", snap, "erp_sync", classify(snap, now, hours), hours),
           Freshness("movements", moves, "erp_sync", classify(moves, now, hours), hours, moves_raw)]
    if latest is not None:                                    # the aggregates carry the origin of what they were built from
        out.append(Freshness("aggregates", latest.refreshed_at, latest.origin, classify(latest.refreshed_at, now, hours), hours))
    return out
