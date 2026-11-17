"""T131: dashboard orchestration. Combines card-level results only (no business rule here); a failing card degrades alone."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from auth.session import SessionData
from clients.forecast import ForecastClient
from clients.inventory import InventoryClient
from clients.procurement import ProcurementClient
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from mmi_common.time import ASSUMED_LOCAL_TZ
from routes.admin_roles import get_store
from routes.api import EXPORT_ROLES, get_inventory_client, get_procurement_client
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
    spend_parts = [{"key": "proposed", "label_key": "dashboard.part.proposed", "value": r["proposed"]}, {"key": "spend", "label_key": "dashboard.part.spend", "value": r["spend"]}]   # never one figure: proposed is before an order is confirmed
    caps = [{"key": "cap_week", "label_key": "dashboard.part.cap_week", "value": w["cap"],
             "period": {"from": w["week_start"], "to": (date.fromisoformat(w["week_start"]) + timedelta(days=6)).isoformat()}} for w in r["weeks"] if w["cap"] is not None]
    if r["budget"] is None:
        return {**_indicator("purchasing_budget", "no_data"), "basis": "dashboard.basis.no_budget", "parts": spend_parts}
    return {**_indicator("purchasing_budget", "ok", r["budget"]), "parts": [*caps, *spend_parts]}


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
    today = datetime.now(ZoneInfo(ASSUMED_LOCAL_TZ)).date()                # the business day is the Madrid date, as inventory reads it
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
    kind: str = Query(pattern="^(inventory_value|coverage|stockout_risk|expiry_risk|abc_xyz|trend_day|demand|forecast|capital|expiry_band)$"),
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
    band: str | None = Query(default=None, pattern="^(expired|d0_30|d31_60)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    session: SessionData = Depends(require_roles(*READ)),
    inv: InventoryClient = Depends(get_inventory_client),
) -> Any:
    """The products behind one dashboard figure. The rules live in inventory; this only checks the request shape and forwards the signed-in user."""
    params = {k: v for k, v in (("kind", kind), ("abc", abc), ("xyz", xyz), ("day", day), ("warehouse_id", warehouse_id), ("category", category), ("family", family), ("supplier_id", supplier_id), ("limit", limit), ("offset", offset), ("sort", sort), ("order", order), ("band", band), ("date_from", date_from and date_from.isoformat()), ("date_to", date_to and date_to.isoformat())) if v is not None}
    return await inv.forward("GET", "/dashboard/drilldown", params=params, user_id=session.user_id, roles=session.roles)


@router.get("/freshness")
async def freshness(session: SessionData = Depends(require_roles(*READ)), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    """How fresh each source is, where it came from, and how many records were left out (counts only). A failing source is a clear error, never an empty or zero answer."""
    try:
        return await inv.forward("GET", "/dashboard/freshness", user_id=session.user_id, roles=session.roles)
    except (httpx.HTTPError, RuntimeError) as exc:
        raise HTTPException(502, "downstream_unavailable") from exc                # no downstream text reaches the user


@router.get("/charts")
async def charts(
    keys: str | None = Query(default=None, pattern="^[a-z_]{1,30}(,[a-z_]{1,30}){0,9}$"),
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: int | None = Query(default=None, ge=0),
    category: str | None = Query(default=None, pattern="^(A|B|C|critical)$"),
    family: str | None = Query(default=None, min_length=1, max_length=120),
    supplier_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_-]{1,36}$"),
    session: SessionData = Depends(require_roles(*READ)),
    inv: InventoryClient = Depends(get_inventory_client),
) -> Any:
    """The chart tables behind the dashboard. Inventory builds them (and leaves out money for roles without cost access); this only checks the request shape and forwards the signed-in user."""
    raw = (("keys", keys), ("date_from", date_from and date_from.isoformat()), ("date_to", date_to and date_to.isoformat()), ("warehouse_id", warehouse_id), ("category", category), ("family", family), ("supplier_id", supplier_id))
    return await inv.forward("GET", "/dashboard/charts", params={k: v for k, v in raw if v is not None}, user_id=session.user_id, roles=session.roles)


def _audit_export(session: SessionData, action: str, kind: str, view: str, filters: dict[str, Any], **after: Any) -> None:
    """One entry in the hash-chained log: who, what and which filters. Never the rows."""
    get_store().record_action(session.user_id, action, f"dashboard.export:{view}", after={"kind": kind, "view": view, "filters": filters, **after})


@router.get("/export")
async def export_dashboard(
    kind: str = Query(pattern="^(cards|chart|drilldown)$"),
    chart: str | None = Query(default=None, pattern="^[a-z_]{1,30}$"),
    drill_kind: str | None = Query(default=None, pattern="^[a-z_]{1,20}$"),
    abc: str | None = Query(default=None, pattern="^[ABC]$"),
    xyz: str | None = Query(default=None, pattern="^[XYZ]$"),
    day: str | None = Query(default=None, pattern="^\\d{4}-\\d{2}-\\d{2}$"),
    band: str | None = Query(default=None, pattern="^(expired|d0_30|d31_60)$"),
    sort: str | None = Query(default=None, pattern="^(sku|name|figure)$"),
    order: str | None = Query(default=None, pattern="^(asc|desc)$"),
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    loaded_at: datetime | None = None,                                       # when the screen loaded its data: passed on, not a filter
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: int | None = Query(default=None, ge=0),
    category: str | None = Query(default=None, pattern="^(A|B|C|critical)$"),
    family: str | None = Query(default=None, min_length=1, max_length=120),
    supplier_id: str | None = Query(default=None, pattern="^[A-Za-z0-9_-]{1,36}$"),
    session: SessionData = Depends(require_roles(*EXPORT_ROLES)),          # a viewer is refused here, and the refusal is audited by the role check
    inv: InventoryClient = Depends(get_inventory_client),
    proc: ProcurementClient = Depends(get_procurement_client),
) -> Response:
    """One view of the dashboard as a file. Inventory builds it from the same code as the screen; this checks the shape, forwards the signed-in user and audits the attempt."""
    scope = (("warehouse_id", warehouse_id), ("category", category), ("family", family), ("supplier_id", supplier_id),
             ("date_from", date_from and date_from.isoformat()), ("date_to", date_to and date_to.isoformat()))
    own = (("kind", kind), ("chart", chart), ("drill_kind", drill_kind), ("abc", abc), ("xyz", xyz), ("day", day), ("band", band), ("sort", sort), ("order", order), ("loaded_at", loaded_at and loaded_at.isoformat()), *scope)
    params = {k: v for k, v in own if v is not None}
    filters = {k: v for k, v in scope if v is not None}
    view = chart or drill_kind or kind
    if format != "csv":                                                      # XLSX is not offered: the writer lives in procurement-service
        _audit_export(session, "dashboard.export.refused", kind, view, filters, reason="format_unsupported")
        raise HTTPException(400, "format_unsupported")
    if kind == "cards":                                                      # capital needs the open orders procurement owns: passed on as the text it came as, summed in inventory
        try:
            spend = await proc.forward("GET", "/summary/spend", user_id=session.user_id, roles=session.roles)
        except (httpx.HTTPError, RuntimeError):
            spend = None
        amount = spend.get("open_orders") if isinstance(spend, dict) else None
        if isinstance(amount, str):
            params["open_orders"] = amount
    res = await inv.get("/dashboard/export", params=params, user_id=session.user_id, roles=session.roles)
    if res.status_code == 413:
        _audit_export(session, "dashboard.export.refused", kind, view, filters, reason="export_too_large")
        raise HTTPException(413, "export_too_large")
    if res.status_code == 422:
        raise HTTPException(422, "request_invalid")
    if res.status_code != 200:
        raise HTTPException(502, "downstream_unavailable")                  # no downstream text reaches the user
    rows = int(res.headers.get("x-export-rows", "0") or 0)
    _audit_export(session, "dashboard.exported", kind, view, filters, rows=rows)
    return Response(res.content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": res.headers.get("content-disposition") or f'attachment; filename="panel-{kind}.csv"'})


@router.get("/skus/{sku}")
async def sku_page(sku: str = Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,59}$"), session: SessionData = Depends(require_roles(*READ)), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    """One product by SKU. Inventory builds the page and leaves the cost out for roles that may not see it; this only checks the SKU shape and forwards the signed-in user."""
    return await inv.forward("GET", f"/dashboard/skus/{sku}", user_id=session.user_id, roles=session.roles)


@router.get("/variants/{variant_id}/forecast-basis")
async def forecast_basis(variant_id: int = Path(ge=1), session: SessionData = Depends(require_roles(*READ)), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    """Whether one product's forecast rests on imported estimates (FR-008); the answer comes from forecast-service."""
    return await fc.forward("GET", f"/forecasts/variant/{variant_id}", user_id=session.user_id, roles=session.roles)
