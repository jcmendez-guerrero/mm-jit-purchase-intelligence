"""T131: dashboard orchestration. Combines card-level results only (no business rule here); a failing card degrades alone."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from auth.session import SessionData
from clients.forecast import ForecastClient
from clients.inventory import InventoryClient
from clients.procurement import ProcurementClient
from fastapi import APIRouter, Depends, Path, Query
from routes.api import get_inventory_client, get_procurement_client
from routes.policies import get_forecast_client
from routes.rbac import require_roles

router = APIRouter(prefix="/dashboard")
READ = ("viewer", "buyer", "approver", "admin")
MONEY_ROLES = frozenset({"buyer", "approver", "admin"})      # same rule as inventory-service dashboard/roles.py (FR-017)


KEYS = ("stock_value", "coverage_days", "demand", "forecast", "stockout_risk", "expiry_exposure", "capital_tied_up", "purchasing_budget", "wape", "bias")
UNITS = {"coverage_days": "days", "demand": "units", "forecast": "units", "stockout_risk": "count", "wape": "percent", "bias": "percent"}      # the others are EUR
SOURCES = {"demand": ("movements", "erp_sync"), "forecast": ("forecast", "forecast"), "purchasing_budget": ("budget_spend", "proposal"), "wape": ("accuracy", "forecast"), "bias": ("accuracy", "forecast")}


def _indicator(key: str, state: str, value: str | None = None, **extra: Any) -> dict[str, Any]:
    source, origin = SOURCES.get(key, ("inventory_snapshot", "erp_sync"))
    return {"key": key, "value": value, "unit": UNITS.get(key, "EUR"), "state": state, "basis": f"dashboard.basis.{state}" if value is None else f"dashboard.basis.{key}",
            "definition_key": f"dashboard.def.{key}", "freshness": {"source": source, "refreshed_at": None, "refreshed_at_original": None, "origin": origin, "state": "error" if state == "error" else "ok"}, **extra}


async def _card(call: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "data": await call}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": "downstream_refused" if 400 <= exc.response.status_code < 500 else "downstream_unavailable"}
    except (httpx.TransportError, RuntimeError):
        return {"ok": False, "error": "downstream_unavailable"}


async def _hidden_by_role() -> dict[str, Any]:
    return {"ok": False, "error": "hidden_by_role"}


async def _supplier_options(proc: ProcurementClient, who: dict[str, Any]) -> list[dict[str, str]]:
    """Supplier options come from the live supplier list (id and name only)."""
    rows = await proc.forward("GET", "/suppliers", **who)
    return [{"id": r["id"], "name": r["name"]} for r in rows]


def budget_indicator(spend: dict[str, Any], can_see_costs: bool) -> dict[str, Any]:
    """FR-026, research R15: the budget is the sum of the weekly caps in the range, shown with each cap and the spend; no cap at all is ``no_data`` that still shows the spend."""
    if not can_see_costs:
        return _indicator("purchasing_budget", "hidden_by_role")
    r = (spend.get("data") or {}).get("range") if spend.get("ok") else None
    if r is None:
        return _indicator("purchasing_budget", "error")
    spend_part = {"key": "spend", "label_key": "dashboard.part.spend", "value": r["spend"]}
    caps = [{"key": "cap_week", "label_key": "dashboard.part.cap_week", "value": w["cap"],
             "period": {"from": w["week_start"], "to": (date.fromisoformat(w["week_start"]) + timedelta(days=6)).isoformat()}} for w in r["weeks"] if w["cap"] is not None]
    if r["budget"] is None:
        return {**_indicator("purchasing_budget", "no_data"), "basis": "dashboard.basis.no_budget", "parts": [spend_part]}
    return {**_indicator("purchasing_budget", "ok", r["budget"]), "parts": [*caps, spend_part]}


def accuracy_indicators(acc: dict[str, Any], unsupported: list[str]) -> list[dict[str, Any]]:
    """WAPE and bias as percentages of the overall group of the latest scored run; company-wide, so the filters present are named as not followed."""
    if not acc.get("ok"):
        return [_indicator("wape", "error"), _indicator("bias", "error")]
    overall = ((acc.get("data") or {}).get("metrics") or {}).get("all") or {}
    out = []
    for key in ("wape", "bias"):
        raw = _money(overall.get(key))
        extra = {"filters_unsupported": unsupported} if unsupported else {}
        out.append(_indicator(key, "no_data", **extra) if raw is None else _indicator(key, "ok", str((raw * 100).quantize(Decimal("0.01"))), **extra))
    return out


def _overview_indicators(inv: dict[str, Any], spend: dict[str, Any], acc: dict[str, Any], roles: Any, filters: dict[str, Any]) -> list[dict[str, Any]]:
    can_see_costs = bool(MONEY_ROLES.intersection(roles))
    six = {i["key"]: i for i in ((inv.get("data") or {}).get("indicators") or []) if inv.get("ok")}
    unsupported = [k.removesuffix("_id") for k in ("warehouse_id", "category", "family") if k in filters]
    capital = _indicator("capital_tied_up", "hidden_by_role") if not can_see_costs else capital_indicator(inv.get("data") or {}, spend.get("data") or {}, unsupported)
    accuracy_unsupported = [k.removesuffix("_id") for k in ("warehouse_id", "supplier_id", "category", "family") if k in filters]
    by = {**{k: six.get(k) or _indicator(k, "error") for k in KEYS[:6]}, "capital_tied_up": capital, "purchasing_budget": budget_indicator(spend, can_see_costs),
          **{i["key"]: i for i in accuracy_indicators(acc, accuracy_unsupported)}}
    return [by[k] for k in KEYS]


@router.get("/overview")
async def overview(
    warehouse_id: int | None = Query(default=None, ge=0),
    category: str | None = Query(default=None, pattern="^(A|B|C|critical)$"),
    family: str | None = Query(default=None, min_length=1, max_length=120),
    days: int = Query(default=60, ge=7, le=365),
    session: SessionData = Depends(require_roles(*READ)),
    inv: InventoryClient = Depends(get_inventory_client),
    proc: ProcurementClient = Depends(get_procurement_client),
    fc: ForecastClient = Depends(get_forecast_client),
    supplier_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_-]{1,36}$"),
) -> dict[str, Any]:
    who = {"user_id": session.user_id, "roles": session.roles}
    f = {k: v for k, v in (("warehouse_id", warehouse_id), ("category", category), ("family", family), ("supplier_id", supplier_id)) if v is not None}
    today = datetime.now(UTC).date()
    window = {"date_from": (today - timedelta(days=days - 1)).isoformat(), "date_to": today.isoformat()}
    summary, trend, abc, risks, options, accuracy, spend, suppliers, indicators = await asyncio.gather(
        _card(inv.forward("GET", "/dashboard/summary", params=f, **who)),
        _card(inv.forward("GET", "/dashboard/demand-trend", params={**f, "days": days}, **who)),
        _card(inv.forward("GET", "/dashboard/abc-xyz", **who)),
        _card(inv.forward("GET", "/risk", params={"warehouse_id": warehouse_id} if warehouse_id is not None else None, **who)),
        _card(inv.forward("GET", "/dashboard/filters/options", **who)),
        _card(fc.forward("GET", "/accuracy", **who)),
        _card(proc.forward("GET", "/summary/spend", params={**({"supplier_id": supplier_id} if supplier_id else {}), **window}, **who)) if MONEY_ROLES.intersection(session.roles) else _hidden_by_role(),
        _card(_supplier_options(proc, who)),
        _card(inv.forward("GET", "/dashboard/indicators", params={**f, **window}, **who)))
    return {"summary": summary, "trend": trend, "abc_xyz": abc, "risks": risks, "options": options, "accuracy": accuracy, "spend": spend, "suppliers": suppliers,
            "indicators": _overview_indicators(indicators, spend, accuracy, session.roles, f)}


def _money(raw: Any) -> Decimal | None:
    try:
        return Decimal(raw) if isinstance(raw, str) else None
    except InvalidOperation:
        return None


def capital_indicator(stock: dict[str, Any], spend: dict[str, Any], unsupported: list[str]) -> dict[str, Any]:
    """FR-025: capital tied up = stock at lot cost + confirmed orders not yet received. Adds two numbers it received; a missing part gives ``error``, never a partial total."""
    ind = next((i for i in stock.get("indicators", []) if i.get("key") == "stock_value"), {})
    held, open_orders = _money(ind.get("value")), _money(spend.get("open_orders"))
    out: dict[str, Any] = {"key": "capital_tied_up", "value": None, "unit": "EUR", "state": "error", "basis": "dashboard.basis.stock_plus_open_orders",
                           "definition_key": "dashboard.def.capital_tied_up",
                           "freshness": ind.get("freshness") or {"source": "inventory_snapshot", "refreshed_at": None, "refreshed_at_original": None, "origin": "erp_sync", "state": "error"}}
    if unsupported:
        out["filters_unsupported"] = unsupported
    if held is None or open_orders is None:
        return out
    return {**out, "value": str((held + open_orders).quantize(Decimal("0.01"))), "state": "stale" if ind.get("state") == "stale" else "ok",
            "parts": [{"key": "stock_at_cost", "label_key": "dashboard.part.stock_at_cost", "value": str(held)},
                      {"key": "open_orders", "label_key": "dashboard.part.open_orders", "value": str(open_orders)}]}


@router.get("/drilldown")
async def drilldown(
    kind: str = Query(pattern="^(inventory_value|coverage|stockout_risk|expiry_risk|abc_xyz|trend_day)$"),
    abc: str | None = Query(default=None, pattern="^[ABC]$"),
    xyz: str | None = Query(default=None, pattern="^[XYZ]$"),
    day: str | None = Query(default=None, pattern="^\\d{4}-\\d{2}-\\d{2}$"),
    warehouse_id: int | None = Query(default=None, ge=0),
    category: str | None = Query(default=None, pattern="^(A|B|C|critical)$"),
    family: str | None = Query(default=None, min_length=1, max_length=120),
    supplier_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_-]{1,36}$"),
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int | None = Query(default=None, ge=0),
    sort: str | None = Query(default=None, pattern="^(sku|name|figure)$"),
    order: str | None = Query(default=None, pattern="^(asc|desc)$"),
    session: SessionData = Depends(require_roles(*READ)),
    inv: InventoryClient = Depends(get_inventory_client),
) -> Any:
    """The products behind one dashboard figure. The rules live in inventory; this only checks the request shape and forwards the signed-in user."""
    params = {k: v for k, v in (("kind", kind), ("abc", abc), ("xyz", xyz), ("day", day), ("warehouse_id", warehouse_id), ("category", category), ("family", family), ("supplier_id", supplier_id), ("limit", limit), ("offset", offset), ("sort", sort), ("order", order)) if v is not None}
    return await inv.forward("GET", "/dashboard/drilldown", params=params, user_id=session.user_id, roles=session.roles)


@router.get("/variants/{variant_id}/forecast-basis")
async def forecast_basis(variant_id: int = Path(ge=1), session: SessionData = Depends(require_roles(*READ)), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    """Whether one product's forecast rests on imported estimates (FR-008); the answer comes from forecast-service."""
    return await fc.forward("GET", f"/forecasts/variant/{variant_id}", user_id=session.user_id, roles=session.roles)
