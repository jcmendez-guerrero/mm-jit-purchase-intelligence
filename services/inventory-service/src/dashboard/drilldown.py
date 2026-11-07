"""T174 (FR-007): the products behind a dashboard figure. Read-only; the same scope, lot valuation and coverage rules as the KPIs, so the rows
add up to the figure shown. Figures are strings (exact decimals); a long list is cut and flagged."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from db.tables import demand_observations, product_segments, variants
from risk.daily import evaluate_risks
from sqlalchemy import select
from sqlalchemy.engine import Connection

from dashboard.kpis import (
    EXPIRY_DAYS,
    Filters,
    ForecastMeans,
    coverage_by_variant,
    valued_lots,
    variant_scope,
)

KINDS = ("inventory_value", "coverage", "stockout_risk", "expiry_risk", "abc_xyz", "trend_day")
DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class DrillError(Exception):
    def __init__(self, code: str = "request_invalid") -> None:
        super().__init__(code)
        self.code = code


def _fmt(v: Decimal, places: str = "0.01") -> str:
    return str(v.quantize(Decimal(places)))


def drilldown(conn: Connection, kind: str, today: date, f: Filters, forecast: ForecastMeans | None = None, abc: str | None = None, xyz: str | None = None,
              day: str | None = None, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    if kind not in KINDS or not 0 < limit <= MAX_LIMIT:
        raise DrillError()
    scope = variant_scope(conn, f)
    figures: list[tuple[int, Decimal | None, str]]            # (variant, sort key, shown figure); sorted by key, descending unless noted
    descending = True
    if kind == "inventory_value":
        total: dict[int, Decimal] = {}
        for vid, value, _est, _exp in valued_lots(conn, today, f, scope):
            total[vid] = total.get(vid, Decimal(0)) + value
        figures = [(v, x, _fmt(x)) for v, x in total.items()]
    elif kind == "coverage":
        per, _without = coverage_by_variant(conn, today, f, scope, forecast)
        figures = [(v, d, _fmt(d)) for v, (d, _b) in per.items()]
        descending = False                                                # fewest days of cover first
    elif kind in ("stockout_risk", "expiry_risk"):
        want = "stockout" if kind == "stockout_risk" else "expiry"
        seen: dict[int, None] = {}
        for r in evaluate_risks(conn, warehouse_id=f.warehouse_id, as_of=today, expiry_horizon_days=EXPIRY_DAYS):
            if r["risk_type"] == want and r["variant_id"] in scope:
                seen[r["variant_id"]] = None
        figures = [(v, Decimal(v), "") for v in seen]
        descending = False
    elif kind == "abc_xyz":
        if abc not in ("A", "B", "C") or xyz not in ("X", "Y", "Z"):
            raise DrillError()
        figures = []
        for r in conn.execute(select(product_segments).where(product_segments.c.abc == abc, product_segments.c.xyz == xyz)).all():
            if r.variant_id in scope:
                value = Decimal(str((r.metrics or {}).get("value", 0)))
                figures.append((r.variant_id, value, _fmt(value)))
    else:                                                                  # trend_day
        try:
            d = date.fromisoformat(day or "")
        except ValueError as exc:
            raise DrillError() from exc
        q = select(demand_observations.c.variant_id, demand_observations.c.demand_qty).where(demand_observations.c.day == d)
        if f.warehouse_id is not None:
            q = q.where(demand_observations.c.warehouse_id == f.warehouse_id)
        units: dict[int, int] = {}
        for r in conn.execute(q).all():
            if r.variant_id in scope:
                units[r.variant_id] = units.get(r.variant_id, 0) + r.demand_qty
        figures = [(v, Decimal(u), str(u)) for v, u in units.items() if u > 0]
    figures.sort(key=lambda t: (-(t[1] or 0) if descending else (t[1] or 0), t[0]))
    shown = figures[:limit]
    info = {r.external_id: r for r in conn.execute(select(variants.c.external_id, variants.c.sku, variants.c.name).where(variants.c.external_id.in_([v for v, _k, _s in shown]))).all()}
    return {"kind": kind, "truncated": len(figures) > limit, "total": len(figures),
            "rows": [{"variant_id": v, "sku": getattr(info.get(v), "sku", None), "name": getattr(info.get(v), "name", None), "figure": s or None} for v, _k, s in shown]}

