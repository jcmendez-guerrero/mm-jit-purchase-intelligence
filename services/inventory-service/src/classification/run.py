"""Compute and store product segments for every variant with reconstructed history."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from db.tables import (
    ALL_WAREHOUSES,
    demand_observations,
    product_segments,
    products,
    stock_history,
    stock_movements,
    variants,
)
from mmi_common.time import utc_now
from sqlalchemy import delete, func, insert, select
from sqlalchemy.engine import Connection

from classification.segments import ClassificationConfig, SeriesInput, assign_abc, classify_series, series_value


def load_series(conn: Connection, through_day: date | None = None) -> list[SeriesInput]:
    through_day = through_day or conn.execute(select(func.max(stock_history.c.day))).scalar_one()
    if through_day is None:
        return []
    demand: dict[int, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for r in conn.execute(select(demand_observations.c.variant_id, demand_observations.c.day, demand_observations.c.demand_qty)).all():
        demand[r.variant_id][r.day] += r.demand_qty
    hist: dict[int, dict[date, tuple[bool, bool]]] = defaultdict(dict)
    for r in conn.execute(select(stock_history.c.variant_id, stock_history.c.day, stock_history.c.censored, stock_history.c.reconciled_ok)
                          .where(stock_history.c.warehouse_id == ALL_WAREHOUSES)).all():
        hist[r.variant_id][r.day] = (bool(r.censored), bool(r.reconciled_ok))
    info = {r.external_id: r for r in conn.execute(select(variants.c.external_id, variants.c.product_id, variants.c.price)).all()}
    status = {r.external_id: r.status for r in conn.execute(select(products.c.external_id, products.c.status)).all()}
    pending = set(conn.execute(select(stock_movements.c.variant_id).where(stock_movements.c.quarantined).distinct()).scalars())
    out: list[SeriesInput] = []
    for vid, per_day in hist.items():
        first = min(per_day)
        n = (through_day - first).days + 1
        days = [first + timedelta(days=i) for i in range(n)]
        v = info.get(vid)
        out.append(SeriesInput(
            variant_id=vid, days=days, demand=[demand[vid].get(d, 0) for d in days], censored=[per_day.get(d, (False, True))[0] for d in days],
            price=Decimal(str(v.price)) if v is not None and v.price is not None else Decimal(0),
            product_discontinued=bool(v and status.get(v.product_id) == "discontinued"),
            history_reconciled=all(ok for _, ok in per_day.values()), pending_review=vid in pending))
    return sorted(out, key=lambda s: s.variant_id)


def compute_segments(conn: Connection, cfg: ClassificationConfig | None = None, through_day: date | None = None,
                     now: datetime | None = None) -> int:
    series = load_series(conn, through_day)
    abc = assign_abc({s.variant_id: series_value(s) for s in series}, cfg)
    run_id, stamp = str(uuid.uuid4()), now or utc_now()
    conn.execute(delete(product_segments))
    rows = []
    for s in series:
        seg = classify_series(s, abc[s.variant_id], cfg)
        rows.append({"variant_id": s.variant_id, "abc": seg.abc, "xyz": seg.xyz, "pattern": seg.pattern, "forecast_eligible": seg.eligible,
                     "reason": ",".join(seg.reasons), "metrics": {**seg.metrics, "value": float(series_value(s))}, "computed_at": stamp, "run_id": run_id})
    if rows:
        conn.execute(insert(product_segments), rows)
    return len(rows)
