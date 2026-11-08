"""Full rebuild of the derived series (demand, flows, history, metrics) from stored movements.

Run after each applied sync, after a review decision and after a cutover change. Small data volumes make a
full rebuild simpler and safer than incremental patches; results are fully determined by the stored movements.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Any

from db.tables import (
    ALL_WAREHOUSES,
    config_loss_cutover,
    data_quality_metrics,
    demand_observations,
    flow_series,
    stock_history,
    stock_movements,
    stock_snapshots,
)
from mmi_common.time import utc_now
from projections.rules import Exclusions, censoring_value
from quality.metrics import metrics
from sqlalchemy import Table, delete, func, insert, select
from sqlalchemy.engine import Connection

from demand.common import DEFAULT_CUTOVER, Mov, local_day
from demand.losses import flows_from_movements
from demand.provider import DemandProvider, MovementsDemandProvider
from demand.stock_history import reconstruct


@dataclass
class RebuildResult:
    through_day: date | None
    demand_rows: int = 0
    flow_rows: int = 0
    history_rows: int = 0
    variants: int = 0


def current_cutover(conn: Connection) -> date:
    row = conn.execute(select(config_loss_cutover.c.effective_date).order_by(config_loss_cutover.c.id.desc()).limit(1)).first()
    return row.effective_date if row else DEFAULT_CUTOVER


def set_cutover(conn: Connection, effective: date, changed_by: str, now: datetime | None = None) -> None:
    """Audited change; the caller rebuilds so history is reclassified."""
    conn.execute(insert(config_loss_cutover).values(effective_date=effective, changed_by=changed_by, changed_at=now or utc_now()))


def load_movements(conn: Connection) -> list[Mov]:
    rows = conn.execute(select(
        stock_movements.c.external_id, stock_movements.c.variant_id, stock_movements.c.warehouse_id,
        stock_movements.c.created_at_utc, stock_movements.c.reason, stock_movements.c.quantity, stock_movements.c.quarantined)).all()
    return [Mov(r.external_id, r.variant_id, r.warehouse_id, local_day(r.created_at_utc), r.reason, r.quantity, bool(r.quarantined)) for r in rows]


CHUNK = 5000


def _insert_chunked(conn: Connection, table: Table, rows: Iterable[dict[str, Any]]) -> None:
    chunk: list[dict[str, Any]] = []
    for row in rows:
        chunk.append(row)
        if len(chunk) >= CHUNK:
            conn.execute(insert(table), chunk)
            chunk = []
    if chunk:
        conn.execute(insert(table), chunk)


def rebuild(conn: Connection, provider: DemandProvider | None = None, through_day: date | None = None) -> RebuildResult:
    movements = load_movements(conn)
    latest = conn.execute(select(func.max(stock_snapshots.c.snapshot_date)).where(stock_snapshots.c.warehouse_id == ALL_WAREHOUSES)).scalar_one()
    if through_day is None:
        through_day = latest - timedelta(days=1) if latest else None
    result = RebuildResult(through_day)
    cutover = current_cutover(conn)

    current: dict[int, int] = {}
    earlier: dict[int, dict[date, int]] = defaultdict(dict)
    if latest is not None:
        for r in conn.execute(select(stock_snapshots).where(stock_snapshots.c.warehouse_id == ALL_WAREHOUSES)).all():
            if r.snapshot_date == latest:
                current[r.variant_id] = r.on_hand
            else:  # a snapshot taken on day S describes the close of S-1
                earlier[r.variant_id][r.snapshot_date - timedelta(days=1)] = r.on_hand

    excluded = Exclusions(conn)
    history = reconstruct(movements, current, through_day, earlier, censoring_value(conn, "min_zero_stock_days")) if through_day else []
    if excluded:                                               # excluded days are not observable demand, whatever the stock was
        history = [replace(h, censored=True) if excluded(h.variant_id, h.day) else h for h in history]
    censored = {(h.variant_id, h.day): h.censored for h in history}
    demand = (provider or MovementsDemandProvider()).daily_demand(movements)
    flows = flows_from_movements(movements, cutover)

    for t in (demand_observations, flow_series, stock_history):
        conn.execute(delete(t))
    # Inserted in bounded chunks: a full rebuild must fit in the small replicas the budget allows (about 1 GiB).
    _insert_chunked(conn, demand_observations, ({"variant_id": d.variant_id, "warehouse_id": d.warehouse_id, "day": d.day, "demand_qty": d.demand_qty,
                                                 "censored": censored.get((d.variant_id, d.day), False) or bool(excluded and excluded(d.variant_id, d.day)),
                                                 "lineage": d.lineage} for d in demand))
    _insert_chunked(conn, flow_series, ({"variant_id": f.variant_id, "warehouse_id": f.warehouse_id, "day": f.day, "flow": f.flow, "qty": f.qty} for f in flows))
    _insert_chunked(conn, stock_history, ({"variant_id": h.variant_id, "warehouse_id": ALL_WAREHOUSES, "day": h.day, "on_hand_reconstructed": h.on_hand,
                                           "censored": h.censored, "reconciled_ok": h.reconciled_ok} for h in history))
    if through_day:
        conn.execute(delete(data_quality_metrics).where(data_quality_metrics.c.day == through_day))
        conn.execute(insert(data_quality_metrics), [{"day": d, "metric": k, "value": v} for (d, k), v in metrics(movements, cutover, through_day).items()])
    result.demand_rows, result.flow_rows, result.history_rows = len(demand), len(flows), len(history)
    result.variants = len({h.variant_id for h in history})
    return result
