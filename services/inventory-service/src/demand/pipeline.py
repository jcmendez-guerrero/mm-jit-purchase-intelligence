"""T148: what happens after a sync is applied. Rebuild the derived series, reclassify, and announce the result.

``variants`` carries the stock totals (a snapshot), ``movements`` the new demand. Either changes the derived data, so both
trigger a rebuild; the snapshot event follows a new snapshot, the demand event follows any rebuild, and forecast-service
starts a run on the latter.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from classification.run import compute_segments
from db.tables import stock_snapshots
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from demand.publisher import BlobWriter, publish_demand_updated, publish_snapshot_created
from demand.rebuild import rebuild

TRIGGER_KINDS = ("movements", "variants", "lots")


@dataclass
class Pipeline:
    writer: BlobWriter
    correlation_id: str

    def after_sync(self, conn: Connection, kind: str, snapshot_date: date) -> dict[str, int]:
        if kind not in TRIGGER_KINDS:
            return {}
        result = rebuild(conn)
        segments = compute_segments(conn)
        out = {"series": result.demand_rows, "segments": segments}
        if kind == "variants":
            n = conn.execute(select(func.count(func.distinct(stock_snapshots.c.variant_id))).where(stock_snapshots.c.snapshot_date == snapshot_date)).scalar_one()
            publish_snapshot_created(conn, self.writer, snapshot_date, int(n), self.correlation_id)
        if result.through_day is not None:
            publish_demand_updated(conn, self.writer, result.through_day, result.demand_rows, self.correlation_id)
        return out
