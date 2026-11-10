"""T023 (feature 006, contract dashboard_indicators.v2): the indicators inventory owns, each with unit, state, basis, definition key and freshness.

Capital tied up adds the open orders procurement owns, passed in by the gateway as a plain amount, so the sum is made here (ADR-023: the gateway does no money
arithmetic). Purchasing budget, WAPE and bias come from other services. Nothing here invents a zero: no data is ``no_data``, a role
without cost access gets ``hidden_by_role`` and no value.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.engine import Connection

from dashboard.filters import FilterSet
from dashboard.freshness import Freshness, inventory_freshness, stale_after_hours
from dashboard.kpis import ForecastMeans, compute_summary, demand_summary, forecast_summary
from dashboard.roles import can_see_money

BASES = {"stock_value": "lot_cost", "expiry_exposure": "lot_cost", "coverage_days": "coverage", "demand": "erp_sales", "forecast": "forecast_28d", "stockout_risk": "risk_rules", "capital_tied_up": "stock_plus_open_orders"}


def _state(own: str, fresh: str) -> str:
    return "no_data" if "no_data" in (own, fresh) else "stale" if fresh == "stale" else own


def _indicator(key: str, value: object, unit: str, own: str, fresh: dict[str, object], incomplete: int | None = None, unsupported: list[str] | None = None,
               hidden: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {"key": key, "value": None if hidden or value is None else str(value), "unit": unit,
                           "state": "hidden_by_role" if hidden else _state(own, str(fresh["state"])),
                           "basis": f"dashboard.basis.{BASES[key]}", "definition_key": f"dashboard.def.{key}", "freshness": fresh}
    if incomplete is not None:
        out["incomplete_count"] = incomplete
    if unsupported:
        out["filters_unsupported"] = unsupported
    return out


def _capital(stock: str | None, open_orders: Decimal | None, snap: dict[str, object], unvalued: int, fs: FilterSet, money: bool) -> dict[str, Any]:
    """FR-025: stock at lot cost plus confirmed orders not yet received. A missing part is an error with no value, never a total made of one part."""
    unsupported = [name for name, present in (("warehouse", fs.warehouse_id is not None), ("category", fs.category is not None), ("family", fs.family is not None)) if present]
    if not money:
        return _indicator("capital_tied_up", None, "EUR", "ok", snap, hidden=True)
    if stock is None or open_orders is None:
        return _indicator("capital_tied_up", None, "EUR", "error" if open_orders is None and snap["state"] != "no_data" else "ok", snap, unsupported=unsupported)
    parts = [{"key": "stock_at_cost", "label_key": "dashboard.part.stock_at_cost", "value": stock}, {"key": "open_orders", "label_key": "dashboard.part.open_orders", "value": str(open_orders.quantize(Decimal("0.01")))}]
    total = None if unsupported else (Decimal(stock) + open_orders).quantize(Decimal("0.01"))             # T099: open orders are company-wide, never add them to a filtered stock
    return {**_indicator("capital_tied_up", total, "EUR", "no_data" if unsupported else "ok", snap, unvalued, unsupported), "parts": parts}


def build_indicators(conn: Connection, today: date, fs: FilterSet, forecast: ForecastMeans | None, roles: Iterable[str], open_orders: Decimal | None = None) -> dict[str, Any]:
    f, days = fs.to_filters(), (fs.date_to - fs.date_from).days + 1
    s = compute_summary(conn, today, f, forecast)
    d = demand_summary(conn, fs.date_to, days, f)
    fc = forecast_summary(conn, today, f, forecast)
    hours = stale_after_hours()
    fresh: dict[str, Freshness] = {x.source: x for x in inventory_freshness(conn, hours=hours)}
    snap, moves = fresh["inventory_snapshot"].as_json(), fresh["movements"].as_json()
    forecast_fresh = {"source": "forecast", "refreshed_at": None, "refreshed_at_original": None, "origin": "forecast", "state": "ok" if fc["state"] == "ok" else "no_data", "stale_after_hours": hours}
    money = can_see_money(roles)
    stock = s.as_json()
    indicators = [
        _indicator("stock_value", stock["inventory_value"], "EUR", "ok", snap, s.unvalued_lots, hidden=not money),
        _indicator("coverage_days", stock["coverage_days_avg"], "days", "ok" if s.coverage_days_avg is not None else "no_data", snap, s.variants_without_demand),
        _indicator("demand", d["units"], "units", d["state"], moves, d["censored_rows"]),
        _indicator("forecast", fc["units"], "units", fc["state"], forecast_fresh, fc["incomplete"], ["warehouse"] if fc["reason"] == "company_wide_only" else None),
        _indicator("stockout_risk", s.stockout_risk, "count", "ok", snap),
        _indicator("expiry_exposure", stock["expiring_value"], "EUR", "ok", snap, hidden=not money),
        _capital(stock["inventory_value"], open_orders, snap, s.unvalued_lots, fs, money),
    ]
    return {"filters": {"date_from": fs.date_from.isoformat(), "date_to": fs.date_to.isoformat(), "warehouse_id": fs.warehouse_id, "supplier_id": fs.supplier_id,
                        "category": fs.category, "family": fs.family}, "indicators": indicators}
