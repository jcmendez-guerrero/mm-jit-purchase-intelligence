"""T131: dashboard orchestration. Combines card-level results only (no business rule here); a failing card degrades alone."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
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
    """WAPE and bias of the overall group of the latest scored run, as the percentages forecast-service sends; company-wide, so the filters present are named as not followed."""
    if not acc.get("ok"):
        return [_indicator("wape", "error"), _indicator("bias", "error")]
    overall = ((acc.get("data") or {}).get("percent") or {}).get("all") or {}
    extra = {"filters_unsupported": unsupported} if unsupported else {}
    return [_indicator(key, "no_data", **extra) if overall.get(key) is None else _indicator(key, "ok", overall[key], **extra) for key in ("wape", "bias")]


def _overview_indicators(inv: dict[str, Any], spend: dict[str, Any], acc: dict[str, Any], roles: Any, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """The ten indicators in order: inventory's seven (capital included, summed there), then budget, WAPE and bias. A failed service leaves its indicators as ``error``."""
    own = {i["key"]: i for i in ((inv.get("data") or {}).get("indicators") or []) if inv.get("ok")}
    accuracy_unsupported = [k.removesuffix("_id") for k in ("warehouse_id", "supplier_id", "category", "family") if k in filters]
    by = {**{k: own.get(k) or _indicator(k, "error") for k in KEYS[:7]}, "purchasing_budget": budget_indicator(spend, bool(MONEY_ROLES.intersection(roles))),
          **{i["key"]: i for i in accuracy_indicators(acc, accuracy_unsupported)}}
    return [by[k] for k in KEYS]


async def _spend_then_indicators(inv: InventoryClient, proc: ProcurementClient, who: dict[str, Any], f: dict[str, Any], window: dict[str, str], supplier_id: str | None,
                                 can_see_costs: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    """Procurement owns the open orders, inventory makes the capital total; the amount is passed through as it came, with no arithmetic here (ADR-023)."""
    spend = await _card(proc.forward("GET", "/summary/spend", params={**({"supplier_id": supplier_id} if supplier_id else {}), **window}, **who)) if can_see_costs else await _hidden_by_role()
    open_orders = (spend.get("data") or {}).get("open_orders") if spend.get("ok") else None
    extra = {"open_orders": open_orders} if isinstance(open_orders, str) else {}
    return spend, await _card(inv.forward("GET", "/dashboard/indicators", params={**f, **window, **extra}, **who))


@router.get("/overview")
async def overview(
    warehouse_id: int | None = Query(default=None, ge=0),
    category: str | None = Query(default=None, pattern="^(A|B|C|critical)$"),
    family: str | None = Query(default=None, min_length=1, max_length=120),
    days: int = Query(default=60, ge=7, le=365),
    date_from: date | None = None,
    date_to: date | None = None,
    session: SessionData = Depends(require_roles(*READ)),
    inv: InventoryClient = Depends(get_inventory_client),
    proc: ProcurementClient = Depends(get_procurement_client),
    fc: ForecastClient = Depends(get_forecast_client),
    supplier_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_-]{1,36}$"),
) -> dict[str, Any]:
    who = {"user_id": session.user_id, "roles": session.roles}
    f = {k: v for k, v in (("warehouse_id", warehouse_id), ("category", category), ("family", family), ("supplier_id", supplier_id)) if v is not None}
    today = datetime.now(UTC).date()
    end = date_to or today                                              # the range rules (order, span) are the domain's; only the missing end is filled here
    window = {"date_from": (date_from or end - timedelta(days=days - 1)).isoformat(), "date_to": end.isoformat()}
    trend_range = window if (date_from or date_to) else {"days": days}
    summary, trend, abc, risks, options, accuracy, (spend, indicators), suppliers = await asyncio.gather(
        _card(inv.forward("GET", "/dashboard/summary", params=f, **who)),
        _card(inv.forward("GET", "/dashboard/demand-trend", params={**f, **trend_range}, **who)),
        _card(inv.forward("GET", "/dashboard/abc-xyz", params={**f, **(window if (date_from or date_to) else {})}, **who)),
        _card(inv.forward("GET", "/risk", params={"warehouse_id": warehouse_id} if warehouse_id is not None else None, **who)),
        _card(inv.forward("GET", "/dashboard/filters/options", **who)),
        _card(fc.forward("GET", "/accuracy", **who)),
        _spend_then_indicators(inv, proc, who, f, window, supplier_id, bool(MONEY_ROLES.intersection(session.roles))),
        _card(_supplier_options(proc, who)))
    return {"summary": summary, "trend": trend, "abc_xyz": abc, "risks": risks, "options": options, "accuracy": accuracy, "spend": spend, "suppliers": suppliers,
            "indicators": _overview_indicators(indicators, spend, accuracy, session.roles, f)}


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
