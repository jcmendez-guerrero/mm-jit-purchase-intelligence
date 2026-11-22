"""Feature 014 (FR-009, FR-010): the analytical charts of the executive dashboard as table rows in the frozen v2 ``ChartSeries`` shape.

Read-only and built from the same helpers as the cards (``valued_lots_dated``, ``coverage_by_variant``, ``demand_trend``), so every chart adds up to a card. The rows are the
chart and the table at once. A chart the data cannot support is ``no_data`` with a reason in ``summary_params``, never an empty or zero-filled series; one chart failing is
``error`` on that chart alone. A role without cost access never receives a money column. ``forecast_error`` is owned by forecast-service and is not served from here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from db.tables import agg_daily_kpis, product_segments
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from dashboard.filters import FilterSet
from dashboard.kpis import (
    ForecastMeans,
    abc_xyz_distribution,
    coverage_by_variant,
    demand_trend,
    forecast_series,
    shared_scope,
    valued_lots_dated,
    variant_scope,
)

log = logging.getLogger(__name__)

CHART_KEYS = ("demand_forecast", "abc_xyz", "expiry_bands", "coverage_buckets", "capital_by_group", "stock_value_history")
BAND_ORDER = ("expired", "d0_30", "d31_60")
COVERAGE_BUCKETS = (("d0_7", 7), ("d8_14", 14), ("d15_30", 30), ("d31_60", 60))
CENT = Decimal("0.01")
ZERO = Decimal(0)


def _money(v: Decimal) -> str:
    return str(v.quantize(CENT))


def _chart(key: str, columns: list[str], rows: list[list[Any]], params: dict[str, Any] | None = None, no_data_reason: str | None = None, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"key": key, "title_key": f"dashboard.chart.title.{key}", "summary_params": dict(params or {}), "columns": columns, "rows": rows,
                           "state": "ok" if rows and no_data_reason is None else "no_data"}
    if no_data_reason is not None:
        out["summary_params"]["reason"] = no_data_reason
        out["rows"] = []
    out.update({k: v for k, v in extra.items() if v is not None})
    return out


def _drop_value(columns: list[str], rows: list[list[Any]]) -> tuple[list[str], list[list[Any]]]:
    at = columns.index("value")
    return [c for i, c in enumerate(columns) if i != at], [[v for i, v in enumerate(r) if i != at] for r in rows]


def demand_forecast(conn: Connection, today: date, fs: FilterSet, forecast: ForecastMeans | None, money: bool) -> dict[str, Any]:
    f = fs.to_filters()
    span = (fs.date_to - fs.date_from).days + 1
    rows: list[list[Any]] = [[p["day"], p["actual"], None, None] for p in demand_trend(conn, fs.date_to, span, f)]
    fc = forecast_series(conn, today, f, forecast) if fs.date_to == today else {"points": [], "reason": "range_in_past"}
    rows += [[p["day"], None, p["mean"], p["upper"]] for p in fc["points"]]
    return _chart("demand_forecast", ["day", "actual", "forecast_mean", "forecast_upper"], rows, {"forecast_reason": fc["reason"]}, None if rows else "no_demand")


def abc_xyz(conn: Connection, today: date, fs: FilterSet, forecast: ForecastMeans | None, money: bool) -> dict[str, Any]:
    cells = abc_xyz_distribution(conn, fs.to_filters())
    columns = ["group", "products", "value"]
    rows = [[f"{c['abc']}{c['xyz']}", c["variant_count"], _money(Decimal(c["value"]))] for c in cells]
    if not money:
        columns, rows = _drop_value(columns, rows)
    unsupported = ["warehouse"] if fs.warehouse_id is not None else []
    return _chart("abc_xyz", columns, rows, {"filters_unsupported": unsupported}, None if rows else "no_segments")


def expiry_bands(conn: Connection, today: date, fs: FilterSet, forecast: ForecastMeans | None, money: bool) -> dict[str, Any]:
    f = fs.to_filters()
    cut30, cut60 = today + timedelta(days=30), today + timedelta(days=60)
    seen = False
    per: dict[str, dict[str, Any]] = {b: {"variants": set(), "value": ZERO} for b in BAND_ORDER}
    for vid, value, _est, expiry in valued_lots_dated(conn, f, variant_scope(conn, f)):
        seen = True
        band = None if expiry is None or expiry > cut60 else "expired" if expiry < today else "d0_30" if expiry <= cut30 else "d31_60"
        if band:
            per[band]["variants"].add(vid)
            per[band]["value"] += value
    columns = ["band", "products", "value"]
    rows = [[b, len(per[b]["variants"]), _money(per[b]["value"])] for b in BAND_ORDER]
    if not money:
        columns, rows = _drop_value(columns, rows)
    return _chart("expiry_bands", columns, rows, {"horizon_days": 60}, None if seen else "no_stock")


def coverage_buckets(conn: Connection, today: date, fs: FilterSet, forecast: ForecastMeans | None, money: bool) -> dict[str, Any]:
    f = fs.to_filters()
    per, without = coverage_by_variant(conn, today, f, variant_scope(conn, f), forecast)
    counts = {name: 0 for name, _ in COVERAGE_BUCKETS} | {"d61_plus": 0}
    for days, _basis in per.values():
        counts[next((name for name, top in COVERAGE_BUCKETS if days <= top), "d61_plus")] += 1
    rows = [[name, n] for name, n in counts.items()] + [["no_demand", without]]
    return _chart("coverage_buckets", ["bucket", "products"], rows, {}, None if per or without else "no_stock")


def capital_by_group(conn: Connection, today: date, fs: FilterSet, forecast: ForecastMeans | None, money: bool) -> dict[str, Any]:
    f = fs.to_filters()
    group_of = {r.variant_id: r.abc for r in conn.execute(select(product_segments.c.variant_id, product_segments.c.abc)).all()}
    per: dict[str, dict[str, Any]] = {}
    seen = False
    for vid, value, _est, _exp in valued_lots_dated(conn, f, variant_scope(conn, f)):
        seen = True
        cell = per.setdefault(group_of.get(vid, "none"), {"variants": set(), "value": ZERO})
        cell["variants"].add(vid)
        cell["value"] += value
    columns = ["group", "products", "value"]
    rows = [[g, len(per[g]["variants"]), _money(per[g]["value"])] for g in ("A", "B", "C", "none") if g in per]
    if not money:
        columns, rows = _drop_value(columns, rows)
    return _chart("capital_by_group", columns, rows, {"part": "stock_at_cost"}, None if seen else "no_stock")


def stock_value_history(conn: Connection, today: date, fs: FilterSet, forecast: ForecastMeans | None, money: bool) -> dict[str, Any]:
    columns = ["day", "value"]
    if not money:
        return _chart("stock_value_history", columns, [], {}, "hidden_by_role")
    if fs.supplier_id is not None or fs.family is not None:
        unsupported = [n for n, v in (("supplier", fs.supplier_id), ("family", fs.family)) if v is not None]
        return _chart("stock_value_history", columns, [], {"filters_unsupported": unsupported}, "filter_not_stored")
    t = agg_daily_kpis.c
    mine = (t.warehouse_id.is_(None) if fs.warehouse_id is None else t.warehouse_id == fs.warehouse_id, t.category_id.is_(None) if fs.category is None else t.category_id == fs.category)
    lo, hi = conn.execute(select(func.min(t.day), func.max(t.day)).where(*mine)).one()
    if lo is None:
        return _chart("stock_value_history", columns, [], {}, "no_history")
    data = conn.execute(select(t.day, t.inventory_value).where(*mine, t.day >= fs.date_from, t.day <= fs.date_to).order_by(t.day)).all()
    rows = [[r.day.isoformat(), _money(Decimal(str(r.inventory_value)))] for r in data]
    return _chart("stock_value_history", columns, rows, {}, None if rows else "range_outside_history", range_available={"from": lo.isoformat(), "to": hi.isoformat()})


BUILDERS: dict[str, Callable[..., dict[str, Any]]] = {
    "demand_forecast": demand_forecast, "abc_xyz": abc_xyz, "expiry_bands": expiry_bands,
    "coverage_buckets": coverage_buckets, "capital_by_group": capital_by_group, "stock_value_history": stock_value_history,
}


def build_charts(conn: Connection, keys: list[str] | tuple[str, ...], today: date, fs: FilterSet, forecast: ForecastMeans | None, money: bool) -> list[dict[str, Any]]:
    """One chart per key, in the order asked. A failing chart is an ``error`` chart (no rows, no downstream text) and never stops the others."""
    out = []
    with shared_scope():
        for key in keys:
            try:
                out.append(BUILDERS[key](conn, today, fs, forecast, money))
            except Exception:
                log.warning("dashboard chart %s failed", key, exc_info=True)
                out.append({"key": key, "title_key": f"dashboard.chart.title.{key}", "columns": [], "rows": [], "state": "error"})
    return out
