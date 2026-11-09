"""T064: supplier-cost update routes. The ERP value is always the median of the lot costs; only an admin can replace it, and
the release is a different buyer's, with fresh MFA. The BFF checks roles and forwards the user identity; the rules live in procurement."""

from __future__ import annotations

from typing import Any

from auth.session import SessionData
from clients.procurement import ProcurementClient
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from routes.api import get_procurement_client
from routes.rbac import require_fresh_mfa, require_roles

router = APIRouter()


class OverrideBody(BaseModel):
    value: str = Field(pattern=r"^\d{1,10}(\.\d{1,4})?$")
    reason: str = Field(min_length=1, max_length=500)


class ReleaseBody(BaseModel):
    acknowledge_variant_conflict: bool = False


@router.get("/lot-costs")
async def list_lot_costs(
    variant_id: int, supplier_id: str,
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> list[dict[str, Any]]:
    return await client.get_lot_costs(variant_id, supplier_id, roles=session.roles)


@router.post("/lot-costs", status_code=201)
async def add_lot_cost(
    body: dict[str, Any],
    session: SessionData = Depends(require_roles("buyer")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.add_lot_cost(body, user_id=session.user_id, roles=session.roles)


@router.post("/cost-updates", status_code=201)
async def request_cost_update(
    body: dict[str, Any],
    session: SessionData = Depends(require_roles("buyer")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.request_cost_update(body, user_id=session.user_id, roles=session.roles)


@router.post("/cost-writes/{write_id}/approve")
async def release_cost_write(
    write_id: str,
    body: ReleaseBody | None = None,
    session: SessionData = Depends(require_fresh_mfa()),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    if "buyer" not in session.roles:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="auth_forbidden_role")
    return await client.approve_cost_write(write_id, user_id=session.user_id, roles=session.roles, body=None if body is None else body.model_dump())


@router.post("/cost-writes/{write_id}/override")
async def override_cost_write(
    write_id: str,
    body: OverrideBody,
    session: SessionData = Depends(require_roles("admin")),
    _fresh: SessionData = Depends(require_fresh_mfa()),         # MMI-6 FR-027: an override is a sensitive ERP-cost operation; the role is checked first
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.override_cost_write(write_id, body.model_dump(), user_id=session.user_id, roles=session.roles)
