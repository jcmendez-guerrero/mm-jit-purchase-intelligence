"""T131: dashboard orchestration. Combines card-level results only (no business rule here); a failing card degrades alone."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from auth.session import SessionData
from clients.forecast import ForecastClient
from clients.inventory import InventoryClient
from clients.procurement import ProcurementClient
from fastapi import APIRouter, Depends, Query
from routes.api import get_inventory_client, get_procurement_client
from routes.policies import get_forecast_client
from routes.rbac import require_roles

router = APIRouter(prefix="/dashboard")
READ = ("viewer", "buyer", "approver", "admin")


async def _card(call: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "data": await call}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": "downstream_refused" if 400 <= exc.response.status_code < 500 else "downstream_unavailable"}
    except (httpx.TransportError, RuntimeError):
        return {"ok": False, "error": "downstream_unavailable"}


async def _supplier_options(proc: ProcurementClient, who: dict[str, Any]) -> list[dict[str, str]]:
    """Supplier options come from the live supplier list (id and name only)."""
    rows = await proc.forward("GET", "/suppliers", **who)
    return [{"id": r["id"], "name": r["name"]} for r in rows]


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
    supplier_id: str | None = Query(default=None, max_length=36),
) -> dict[str, Any]:
    who = {"user_id": session.user_id, "roles": session.roles}
    f = {k: v for k, v in (("warehouse_id", warehouse_id), ("category", category), ("family", family)) if v is not None}
    summary, trend, abc, risks, options, accuracy, spend, suppliers = await asyncio.gather(
        _card(inv.forward("GET", "/dashboard/summary", params=f, **who)),
        _card(inv.forward("GET", "/dashboard/demand-trend", params={**f, "days": days}, **who)),
        _card(inv.forward("GET", "/dashboard/abc-xyz", **who)),
        _card(inv.forward("GET", "/risk", params={"warehouse_id": warehouse_id} if warehouse_id is not None else None, **who)),
        _card(inv.forward("GET", "/dashboard/filters/options", **who)),
        _card(fc.forward("GET", "/accuracy", **who)),
        _card(proc.forward("GET", "/summary/spend", params={"supplier_id": supplier_id} if supplier_id else None, **who)),
        _card(_supplier_options(proc, who)))
    return {"summary": summary, "trend": trend, "abc_xyz": abc, "risks": risks, "options": options, "accuracy": accuracy, "spend": spend, "suppliers": suppliers}
