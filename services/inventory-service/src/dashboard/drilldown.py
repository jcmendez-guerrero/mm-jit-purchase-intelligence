"""T174 (FR-007): the products behind a dashboard figure. Read-only; the same scope, lot valuation and coverage rules as the KPIs, so the rows
add up to the figure shown. Figures are strings (exact decimals); a long list is cut and flagged."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from db.tables import demand_observations, product_segments, variants
from risk.daily import evaluate_risks
from sqlalchemy import select
from sqlalchemy.engine import Connection

from dashboard.kpis import (
    EXPIRY_DAYS,
    FORECAST_DAYS,
    Filters,
    ForecastMeans,
    coverage_by_variant,
    valued_lots_dated,
    variant_scope,
)

KINDS = ("inventory_value", "coverage", "stockout_risk", "expiry_risk", "abc_xyz", "trend_day", "demand", "forecast", "capital", "expiry_band")
BANDS = ("expired", "d0_30", "d31_60")       # the 60-day expiry horizon of the card, cut in three; together they equal the expiring value
MAX_DEMAND_DAYS = 730
DEFAULT_LIMIT = 50
SORTS = ("sku", "name", "figure")      # the only columns a caller may sort by; ties always fall back to SKU ascending
MAX_LIMIT = 200


class DrillError(Exception):
    def __init__(self, code: str = "request_invalid") -> None:
        super().__init__(code)
        self.code = code


def _fmt(v: Decimal, places: str = "0.01") -> str:
    return str(v.quantize(Decimal(places)))


def drilldown(conn: Connection, kind: str, today: date, f: Filters, forecast: ForecastMeans | None = None, abc: str | None = None, xyz: str | None = None,
              day: str | None = None, limit: int = DEFAULT_LIMIT, offset: int = 0, sort: str | None = None, order: str | None = None, days: int | None = None, band: str | None = None, end: date | None = None) -> dict[str, Any]:
    if (kind not in KINDS or not 0 < limit <= MAX_LIMIT or offset < 0 or sort not in (None, *SORTS) or order not in (None, "asc", "desc")
            or (order is not None and sort is None)):
        raise DrillError()
    scope = variant_scope(conn, f)
    figures: list[tuple[int, Decimal | None, str]]            # (variant, sort key, shown figure); sorted by key, descending unless noted
    descending = True
    forecast_sum: str | None = None
    if kind in ("inventory_value", "capital"):          # capital lists its stock part: the open orders are procurement's and have no SKU rows
        total: dict[int, Decimal] = {}
        for vid, value, _est, _exp in valued_lots_dated(conn, f, scope):
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
    elif kind == "expiry_band":
        if band not in BANDS:
            raise DrillError()
        cut30, cut60 = today + timedelta(days=30), today + timedelta(days=60)
        want = {"expired": lambda e: e < today, "d0_30": lambda e: today <= e <= cut30, "d31_60": lambda e: cut30 < e <= cut60}[band]
        by_variant: dict[int, Decimal] = {}
        for vid, value, _est, expiry in valued_lots_dated(conn, f, scope):
            if expiry is not None and want(expiry):
                by_variant[vid] = by_variant.get(vid, Decimal(0)) + value
        figures = [(v, x, _fmt(x)) for v, x in by_variant.items()]
    elif kind == "demand":
        if days is None or not 0 < days <= MAX_DEMAND_DAYS:
            raise DrillError()
        last = end or today
        dq = select(demand_observations.c.variant_id, demand_observations.c.demand_qty, demand_observations.c.censored).where(
            demand_observations.c.day > last - timedelta(days=days), demand_observations.c.day <= last)
        if f.warehouse_id is not None:
            dq = dq.where(demand_observations.c.warehouse_id == f.warehouse_id)
        sold: dict[int, int] = {}
        for r in conn.execute(dq).all():
            if r.variant_id in scope and not r.censored:         # the card leaves censored days out (stock-outs), so the rows do too
                sold[r.variant_id] = sold.get(r.variant_id, 0) + r.demand_qty
        figures = [(v, Decimal(u), str(u)) for v, u in sold.items() if u > 0]
    elif kind == "forecast":
        if forecast is None:
            raise DrillError("no_forecast")
        if f.warehouse_id is not None:
            raise DrillError("company_wide_only")                # the forecast is company-wide, as on the card
        try:
            means = {v: Decimal(str(b[0])) for v, b in (forecast.daily_bands() if hasattr(forecast, "daily_bands") else {v: (m,) for v, m in forecast.daily_means().items()}).items()}
        except Exception as exc:
            raise DrillError("no_forecast") from exc
        use = {v: m for v, m in means.items() if v in scope}
        if not use:
            raise DrillError("no_forecast")
        figures = [(v, m * FORECAST_DAYS, _fmt(m * FORECAST_DAYS)) for v, m in use.items()]
        forecast_sum = _fmt(sum(use.values(), Decimal(0)).quantize(Decimal("0.01")) * FORECAST_DAYS)     # the card adds the same rounded daily point for each day
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
    info = {r.external_id: r for r in conn.execute(select(variants.c.external_id, variants.c.sku, variants.c.name)).all()}
    sku_of = lambda v: getattr(info.get(v), "sku", None) or ""                      # noqa: E731 - ties are broken by SKU, then id, so pages never shuffle
    if sort is None:
        figures.sort(key=lambda t: (-(t[1] or 0) if descending else (t[1] or 0), sku_of(t[0]), t[0]))
    elif sort == "figure":
        flip = order == "desc"
        figures.sort(key=lambda t: (-(t[1] or 0) if flip else (t[1] or 0), sku_of(t[0]), t[0]))      # a descending figure keeps ties in SKU ascending order
    else:
        text = sku_of if sort == "sku" else (lambda v: (getattr(info.get(v), "name", None) or "").lower())
        figures.sort(key=lambda t: (text(t[0]), sku_of(t[0]), t[0]), reverse=order == "desc")
    shown = figures[offset:offset + limit]
    total_sum = None                                                       # the rows add up to the figure: the sum covers every row, not only this page
    if kind in ("inventory_value", "abc_xyz", "capital", "expiry_band"):
        total_sum = _fmt(sum((k or Decimal(0) for _v, k, _s in figures), Decimal(0)))
    elif kind == "forecast":
        total_sum = forecast_sum
    elif kind in ("trend_day", "demand"):
        total_sum = str(int(sum((k or Decimal(0) for _v, k, _s in figures), Decimal(0))))
    return {"kind": kind, "truncated": offset + limit < len(figures), "total": len(figures), "offset": offset, "sum": total_sum,
            "rows": [{"variant_id": v, "sku": getattr(info.get(v), "sku", None), "name": getattr(info.get(v), "name", None), "figure": s or None} for v, _k, s in shown]}

