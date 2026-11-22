"""T026: data-quality routes (feature 018). Orchestration and access control only: every rule lives in inventory-service.

Reads are open to any signed-in role. Buyers and admins may decide anomalies and start a recompute. Excluding an anomalous day, and
reversing an exclusion, needs a second factor authenticated within five minutes (spec FR-004); accepting a day as normal does not.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from urllib.parse import quote

from auth.session import SessionData
from clients.forecast import ForecastClient
from clients.inventory import InventoryClient
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from routes.api import get_inventory_client
from routes.policies import get_forecast_client
from routes.rbac import require_roles

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
async def decide_anomaly(sku: str, day: date, body: DecisionBody, session: SessionData = Depends(require_roles(*EDIT)),
                         inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    fresh = session.is_mfa_fresh(max_age_seconds=MFA_MAX_AGE)      # inventory-service decides which decisions need it; the gateway only reports the fact
    return await inv.forward("PUT", f"{_base(sku)}/anomalies/{day.isoformat()}", json=body.model_dump(), user_id=session.user_id, roles=session.roles,
                             extra_headers={"X-Fresh-Second-Factor": "true" if fresh else "false"})


@router.post("/recompute")
async def recompute(session: SessionData = Depends(require_roles(*EDIT)), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("POST", "/quality/recompute", user_id=session.user_id, roles=session.roles)


ORIGIN = "^(erp|local_export)$"                                   # the two data origins; counts are never summed across them


def _only_set(**values: Any) -> dict[str, Any] | None:
    return {k: v for k, v in values.items() if v is not None} or None


@router.get("/portfolio")
async def portfolio(category: str | None = Query(default=None, max_length=12), supplier_id: str | None = Query(default=None, max_length=36),
                    family: str | None = Query(default=None, max_length=120), origin: str | None = Query(default=None, pattern=ORIGIN),
                    session: SessionData = Depends(require_roles(*READ)), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    """T063: the catalogue-wide distribution of demand classes, eligibility and confidence. Composed and counted by inventory-service."""
    return await inv.forward("GET", "/quality/portfolio", params=_only_set(category=category, supplier_id=supplier_id, family=family, origin=origin), user_id=session.user_id, roles=session.roles)


@router.get("/portfolio/products")
async def portfolio_products(bucket: str = Query(max_length=12), key: str = Query(max_length=40), category: str | None = Query(default=None, max_length=12),
                             supplier_id: str | None = Query(default=None, max_length=36), family: str | None = Query(default=None, max_length=120),
                             limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), origin: str | None = Query(default=None, pattern=ORIGIN),
                             session: SessionData = Depends(require_roles(*READ)), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    params = _only_set(bucket=bucket, key=key, category=category, supplier_id=supplier_id, family=family, limit=limit, offset=offset, origin=origin)
    return await inv.forward("GET", "/quality/portfolio/products", params=params, user_id=session.user_id, roles=session.roles)


class BacktestBody(BaseModel):
    scope: Literal["catalogue", "product"]
    sku: str | None = Field(default=None, max_length=60)


@forecast_router.post("/backtests")
async def start_backtest(body: BacktestBody, session: SessionData = Depends(require_roles(*EDIT)), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    """T056: score one product's method or the whole catalogue's against the baseline. Changes no forecast or proposal; forecast-service enforces one catalogue run at a time."""
    return await fc.forward("POST", "/forecasts/backtests", json=body.model_dump(), user_id=session.user_id, roles=session.roles)


@forecast_router.get("/products/{sku}/backtest")
async def product_backtest(sku: str, session: SessionData = Depends(require_roles(*READ)), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    return await fc.forward("GET", f"/forecasts/products/{quote(sku, safe='')}/backtest", user_id=session.user_id, roles=session.roles)


@forecast_router.get("/products/{sku}/explanation")
async def explanation(sku: str, run_id: str | None = Query(default=None, max_length=36), session: SessionData = Depends(require_roles(*READ)),
                      fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    """T038: why this product's forecast is what it is. Forwarded as is; forecast-service owns the content."""
    params = {"run_id": run_id} if run_id else None
    return await fc.forward("GET", f"/forecasts/products/{quote(sku, safe='')}/explanation", params=params, user_id=session.user_id, roles=session.roles)
