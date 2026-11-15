"""T026: data-quality routes (feature 012). Orchestration and access control only: every rule lives in inventory-service.

Reads are open to any signed-in role. Buyers and admins may decide anomalies and start a recompute. Excluding an anomalous day, and
reversing an exclusion, needs a second factor authenticated within five minutes (spec FR-004); accepting a day as normal does not.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import quote

from auth.session import SessionData
from clients.forecast import ForecastClient
from clients.inventory import InventoryClient
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from routes.api import get_inventory_client
from routes.policies import get_forecast_client
from routes.rbac import log_refusal, require_roles

router = APIRouter(prefix="/quality", tags=["quality"])
forecast_router = APIRouter(prefix="/forecast", tags=["quality"])
READ = ("viewer", "buyer", "approver", "admin")
EDIT = ("buyer", "admin")
MFA_MAX_AGE = 300


class DecisionBody(BaseModel):
    decision: str
    reason_code: str | None = None


def _base(sku: str) -> str:
    return f"/quality/products/{quote(sku, safe='')}"          # never lets a SKU change the downstream path


@router.get("/products/{sku}")
async def summary(sku: str, from_day: date | None = Query(default=None, alias="from"), to_day: date | None = Query(default=None, alias="to"),
                  session: SessionData = Depends(require_roles(*READ)), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    params = {k: v.isoformat() for k, v in (("from", from_day), ("to", to_day)) if v is not None}
    return await inv.forward("GET", _base(sku), params=params or None, user_id=session.user_id, roles=session.roles)


@router.get("/products/{sku}/anomalies")
async def anomalies(sku: str, session: SessionData = Depends(require_roles(*READ)), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("GET", f"{_base(sku)}/anomalies", user_id=session.user_id, roles=session.roles)


@router.put("/products/{sku}/anomalies/{day}")
async def decide_anomaly(sku: str, day: date, body: DecisionBody, request: Request, session: SessionData = Depends(require_roles(*EDIT)),
                         inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    needs_second_factor = body.decision == "excluded"
    if not needs_second_factor and body.decision == "accepted":
        current = await inv.forward("GET", f"{_base(sku)}/anomalies", user_id=session.user_id, roles=session.roles)      # accepting a day that was excluded reverses it
        needs_second_factor = any(a.get("day") == day.isoformat() and a.get("decision") == "excluded" for a in current.get("anomalies", []))
    if needs_second_factor and not session.is_mfa_fresh(max_age_seconds=MFA_MAX_AGE):
        log_refusal(request, session.user_id, session.roles, [], "forbidden_mfa_stale")
        raise HTTPException(status_code=403, detail="auth_mfa_stale")
    return await inv.forward("PUT", f"{_base(sku)}/anomalies/{day.isoformat()}", json=body.model_dump(), user_id=session.user_id, roles=session.roles)


@router.post("/recompute")
async def recompute(session: SessionData = Depends(require_roles(*EDIT)), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("POST", "/quality/recompute", user_id=session.user_id, roles=session.roles)


@forecast_router.get("/products/{sku}/explanation")
async def explanation(sku: str, run_id: str | None = Query(default=None, max_length=36), session: SessionData = Depends(require_roles(*READ)),
                      fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    """T038: why this product's forecast is what it is. Forwarded as is; forecast-service owns the content."""
    params = {"run_id": run_id} if run_id else None
    return await fc.forward("GET", f"/forecasts/products/{quote(sku, safe='')}/explanation", params=params, user_id=session.user_id, roles=session.roles)
