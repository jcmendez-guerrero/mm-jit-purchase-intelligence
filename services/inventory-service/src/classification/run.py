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
    segment_history,
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
        record_history(conn, rows, run_id, stamp)
    return len(rows)


def record_history(conn: Connection, rows: list[dict], run_id: str, stamp: datetime) -> int:
    """Append a history row when a variant's category (ABC, XYZ, pattern) or its manual criticality changed since the last one, with the reason.
    The criticality shown is the manual flag; it is never derived from demand."""
    latest_ids = select(func.max(segment_history.c.id)).group_by(segment_history.c.variant_id)
    last = {r.variant_id: r for r in conn.execute(select(segment_history).where(segment_history.c.id.in_(latest_ids))).all()}
    manual = {p.external_id: bool(p.clinical_critical) for p in conn.execute(select(products.c.external_id, products.c.clinical_critical)).all()}
    crit = {v.external_id: manual.get(v.product_id, False) for v in conn.execute(select(variants.c.external_id, variants.c.product_id)).all()}
    new = []
    for r in rows:
        c = crit.get(r["variant_id"], False)
        prev = last.get(r["variant_id"])
        if prev is None:
            reason = "first_classification"
        else:
            changed = [name for name, a, b in (("abc", prev.abc, r["abc"]), ("xyz", prev.xyz, r["xyz"]), ("pattern", prev.pattern, r["pattern"]), ("criticality", bool(prev.critical), c)) if a != b]
            if not changed:
                continue
            reason = f"{changed[0]}_changed" if len(changed) == 1 else "multiple_changed"
        new.append({"variant_id": r["variant_id"], "changed_at": stamp, "abc": r["abc"], "xyz": r["xyz"], "pattern": r["pattern"], "critical": c, "reason_key": reason, "run_id": run_id})
    if new:
        conn.execute(insert(segment_history), new)
    return len(new)


def history_for(conn: Connection, variant_id: int) -> list[dict]:
    return [{"changed_at": r.changed_at.isoformat(), "abc": r.abc, "xyz": r.xyz, "pattern": r.pattern, "critical": bool(r.critical), "reason_key": r.reason_key, "run_id": r.run_id}
            for r in conn.execute(select(segment_history).where(segment_history.c.variant_id == variant_id).order_by(segment_history.c.id)).all()]
