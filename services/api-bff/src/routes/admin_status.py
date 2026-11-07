"""T151: the admin status page and safe re-runs. Gathers what other services expose; holds no business rule and no cross-schema access.

Each section degrades alone. A re-run is admin only, goes through the owning service (which is idempotent), and is audited here.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

import httpx
from auth.session import SessionData
from clients.forecast import ForecastClient
from clients.inventory import InventoryClient
from clients.procurement import ProcurementClient
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from routes.admin_roles import _mirror_pass, get_store
from routes.api import get_inventory_client, get_procurement_client
from routes.policies import get_forecast_client
from routes.rbac import require_roles

router = APIRouter(prefix="/admin", tags=["admin"])
JOB_ID = re.compile(r"^[0-9a-fA-F-]{8,40}$")
BUDGET_EUR = 120


async def _card(call: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "data": await call}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": "downstream_refused" if 400 <= exc.response.status_code < 500 else "downstream_unavailable"}
    except (httpx.TransportError, RuntimeError):
        return {"ok": False, "error": "downstream_unavailable"}


async def _local(fn: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "data": await asyncio.to_thread(fn)}
    except Exception:
        return {"ok": False, "error": "downstream_unavailable"}


def cost_indicators() -> dict[str, Any]:
    """Guardrail figures from configuration, never from a cloud API: the estimate lives in the architecture document."""
    return {"budget_eur": BUDGET_EUR, "estimate_eur": float(os.environ.get("MMI_COST_ESTIMATE_EUR", "0") or 0),
            "guardrails": {"min_replicas": 0, "max_replicas": 1, "job_parallelism": 1}}


@router.get("/status")
async def status(session: SessionData = Depends(require_roles("admin")), inv: InventoryClient = Depends(get_inventory_client),
                 proc: ProcurementClient = Depends(get_procurement_client), fc: ForecastClient = Depends(get_forecast_client)) -> dict[str, Any]:
    who = {"user_id": session.user_id, "roles": session.roles}
    freshness, jobs, runs, policy, mirror = await asyncio.gather(
        _card(inv.forward("GET", "/status/sources", **who)), _card(fc.forward("GET", "/imports/jobs", **who)),
        _card(fc.forward("GET", "/runs", params={"limit": 10}, **who)), _card(proc.forward("GET", "/policy-overrides", params={"status": "all"}, **who)),
        _local(get_store().mirror_status))
    return {"freshness": freshness, "import_jobs": jobs, "model_runs": runs, "policy_history": policy, "role_mirror": mirror, "cost": cost_indicators()}


def _audit(session: SessionData, subject: str, outcome: dict[str, Any]) -> None:
    get_store().record_action(session.user_id, "admin.rerun", subject, after={k: outcome.get(k) for k in ("reused", "state", "requeued") if k in outcome})


@router.post("/rerun/forecast", status_code=202)
async def rerun_forecast(session: SessionData = Depends(require_roles("admin")), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    out = await fc.forward("POST", "/runs", user_id=session.user_id, roles=session.roles)
    _audit(session, "forecast", out)
    return out


@router.post("/rerun/import/{job_id}", status_code=202)
async def rerun_import(job_id: str, session: SessionData = Depends(require_roles("admin")), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    if not JOB_ID.match(job_id):
        raise HTTPException(422, "request_invalid")
    out = await fc.forward("POST", f"/imports/jobs/{job_id}/rerun", user_id=session.user_id, roles=session.roles)
    _audit(session, "import", out)
    return out


@router.post("/rerun/mirror", status_code=202)
def rerun_mirror(background: BackgroundTasks, session: SessionData = Depends(require_roles("admin"))) -> dict[str, Any]:
    out = {"requeued": get_store().requeue_failed()}
    background.add_task(_mirror_pass)
    _audit(session, "mirror", out)
    return out
