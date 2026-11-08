"""T087 / T091 / T095: the policy console. Three independently revisioned sections, composed here and owned by their services:

* purchasing  (procurement-service): service levels, safety stock, min/max, cadence, budget caps, stocking settings, override requests
* demand      (inventory-service): demand exclusions, censoring rules, clinical criticality, category history
* forecast    (forecast-service): approved model parameters

The BFF checks roles and forwards the signed-in user with the revision the editor read (If-Match); it holds no business rule.
"""

from __future__ import annotations

from typing import Any

import httpx
from auth.session import SessionData
from clients.forecast import ForecastClient
from clients.inventory import InventoryClient
from clients.procurement import ProcurementClient
from fastapi import APIRouter, Depends, Header
from routes.api import get_inventory_client, get_procurement_client
from routes.rbac import require_roles

router = APIRouter()
_forecast = ForecastClient()
ANY = ("viewer", "buyer", "approver", "admin")


def get_forecast_client() -> ForecastClient:
    return _forecast


async def _section(call: Any) -> dict[str, Any]:
    """One section failing must not hide the others: the console shows which part is unavailable."""
    try:
        return {"ok": True, "data": await call}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "error": "downstream_refused" if 400 <= exc.response.status_code < 500 else "downstream_unavailable"}
    except (httpx.TransportError, RuntimeError):
        return {"ok": False, "error": "downstream_unavailable"}


@router.get("/policy-console")
async def policy_console(
    session: SessionData = Depends(require_roles("viewer")),
    proc: ProcurementClient = Depends(get_procurement_client),
    inv: InventoryClient = Depends(get_inventory_client),
    fc: ForecastClient = Depends(get_forecast_client),
) -> dict[str, Any]:
    r, u = session.roles, session.user_id
    return {
        "purchasing": await _section(proc.forward("GET", "/policies", user_id=u, roles=r)),
        "demand": await _section(inv.forward("GET", "/demand-rules", user_id=u, roles=r)),
        "forecast": await _section(fc.forward("GET", "/parameters", user_id=u, roles=r)),
    }


# ---- purchasing -----------------------------------------------------------------------------------------------------------------

@router.get("/policies/{scope}/{key}")
async def get_policy(scope: str, key: str, session: SessionData = Depends(require_roles("viewer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("GET", f"/policies/{scope}/{key}", user_id=session.user_id, roles=session.roles)


@router.put("/policies/{scope}/{key}")
async def put_policy(scope: str, key: str, body: dict[str, Any], if_match: str | None = Header(default=None), session: SessionData = Depends(require_roles("buyer")),
                     proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("PUT", f"/policies/{scope}/{key}", json=body, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.post("/policies/{scope}/{key}/preview")
async def preview_policy(scope: str, key: str, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer")),
                         proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("POST", f"/policies/{scope}/{key}/preview", json=body, user_id=session.user_id, roles=session.roles)


@router.put("/budget-caps")
async def put_budget(body: dict[str, Any], session: SessionData = Depends(require_roles("buyer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("PUT", "/budget-caps", json=body, user_id=session.user_id, roles=session.roles)


@router.get("/stocking/{variant_id}")
async def get_stocking(variant_id: int, session: SessionData = Depends(require_roles("viewer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("GET", f"/stocking/{variant_id}", user_id=session.user_id, roles=session.roles)


@router.put("/stocking/{variant_id}")
async def put_stocking(variant_id: int, body: dict[str, Any], if_match: str | None = Header(default=None), session: SessionData = Depends(require_roles("buyer")),
                       proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("PUT", f"/stocking/{variant_id}", json=body, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.get("/policy-overrides")
async def list_overrides(status: str = "pending", session: SessionData = Depends(require_roles("viewer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("GET", "/policy-overrides", params={"status": status}, user_id=session.user_id, roles=session.roles)


@router.get("/policy-overrides/recommendation/{variant_id}")
async def recommendation(variant_id: int, session: SessionData = Depends(require_roles("viewer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("GET", f"/policy-overrides/recommendation/{variant_id}", user_id=session.user_id, roles=session.roles)


@router.post("/policy-overrides", status_code=201)
async def create_override(body: dict[str, Any], session: SessionData = Depends(require_roles("buyer")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("POST", "/policy-overrides", json=body, user_id=session.user_id, roles=session.roles)


@router.post("/policy-overrides/{rid}/approve")
async def approve_override(rid: str, session: SessionData = Depends(require_roles("approver")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("POST", f"/policy-overrides/{rid}/approve", json={}, user_id=session.user_id, roles=session.roles)


@router.post("/policy-overrides/{rid}/reject")
async def reject_override(rid: str, session: SessionData = Depends(require_roles("approver")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("POST", f"/policy-overrides/{rid}/reject", json={}, user_id=session.user_id, roles=session.roles)


@router.post("/policy-overrides/{rid}/revert")
async def revert_override(rid: str, session: SessionData = Depends(require_roles("buyer", "approver")), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("POST", f"/policy-overrides/{rid}/revert", json={}, user_id=session.user_id, roles=session.roles)


# ---- demand rules, criticality, category history (inventory) --------------------------------------------------------------------

@router.get("/criticality")
async def criticality(session: SessionData = Depends(require_roles("viewer")), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("GET", "/criticality", user_id=session.user_id, roles=session.roles)


@router.put("/products/{product_id}/criticality")
async def set_criticality(product_id: int, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer")), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("PUT", f"/products/{product_id}/criticality", json=body, user_id=session.user_id, roles=session.roles)


@router.post("/demand-rules/exclusions", status_code=201)
async def add_exclusion(body: dict[str, Any], session: SessionData = Depends(require_roles("buyer")), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("POST", "/demand-rules/exclusions", json=body, user_id=session.user_id, roles=session.roles)


@router.put("/demand-rules/exclusions/{xid}")
async def toggle_exclusion(xid: int, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer")), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("PUT", f"/demand-rules/exclusions/{xid}", json=body, user_id=session.user_id, roles=session.roles)


@router.put("/demand-rules/rules/{rule}")
async def put_rule(rule: str, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer")), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("PUT", f"/demand-rules/rules/{rule}", json=body, user_id=session.user_id, roles=session.roles)


@router.get("/segments/{variant_id}/history")
async def segment_history(variant_id: int, session: SessionData = Depends(require_roles("viewer")), inv: InventoryClient = Depends(get_inventory_client)) -> Any:
    return await inv.forward("GET", f"/segments/{variant_id}/history", user_id=session.user_id, roles=session.roles)


# ---- forecast parameters ---------------------------------------------------------------------------------------------------------

@router.put("/parameters/{key}")
async def put_parameter(key: str, body: dict[str, Any], if_match: str | None = Header(default=None), session: SessionData = Depends(require_roles("buyer")),
                        fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    return await fc.forward("PUT", f"/parameters/{key}", json=body, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.post("/forecast/runs", status_code=202)
async def request_forecast(session: SessionData = Depends(require_roles("buyer")), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    return await fc.forward("POST", "/runs", json={}, user_id=session.user_id, roles=session.roles)
