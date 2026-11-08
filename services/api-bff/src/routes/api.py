"""BFF aggregation routes per specs/001-mmi-purchase-intelligence/contracts/bff-api.openapi.yaml (T111)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

from auth import entra
from auth.session import (
    SessionData,
    clear_session_cookie,
    create_session,
    set_session_cookie,
)
from clients.inventory import InventoryClient
from clients.procurement import ProcurementClient
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from routes.admin_roles import has_at_least_two_eligible_approvers
from routes.rbac import require_fresh_mfa, require_roles, require_session

logger = logging.getLogger("mmi.api_bff.routes")

router = APIRouter()

_inventory_client = InventoryClient()
_procurement_client = ProcurementClient()


def get_inventory_client() -> InventoryClient:
    return _inventory_client


def get_procurement_client() -> ProcurementClient:
    return _procurement_client


class DevLoginBody(BaseModel):
    user_id: str = "buyer-1"
    email: str = "buyer1@example.invalid"
    roles: list[str] = Field(default_factory=lambda: ["viewer", "buyer"])


# --- Authentication / Session endpoints ---

def dev_login_enabled() -> bool:
    """Off unless explicitly enabled, and never in production: the endpoint mints a session for a caller-chosen user."""
    return os.environ.get("MMI_ENABLE_DEV_LOGIN") == "1" and os.environ.get("MMI_ENV", "dev") != "prod"


@router.get("/auth/config")
def auth_config() -> dict[str, Any]:
    """Public: which sign-in the login page offers. Development role chooser, Entra ID, or none configured."""
    if dev_login_enabled():
        return {"mode": "dev"}
    return {"mode": "entra" if entra.entra_config() else "none"}


def _login_failed(code: str) -> RedirectResponse:
    resp = RedirectResponse(f"/?login_error={code}", status_code=303)
    resp.delete_cookie(entra.STATE_COOKIE, path="/api/auth")
    return resp


@router.get("/auth/login")
def entra_login() -> Response:
    cfg = entra.entra_config()
    if cfg is None or dev_login_enabled():
        raise HTTPException(status_code=404, detail="not_found")
    url, cookie = entra.begin(cfg)
    resp = RedirectResponse(url, status_code=303)
    secure = os.environ.get("MMI_ENV", "dev") == "prod" or os.environ.get("MMI_COOKIE_SECURE", "").lower() in ("1", "true")
    resp.set_cookie(entra.STATE_COOKIE, cookie, max_age=entra.STATE_TTL_SECONDS, httponly=True, samesite="lax", secure=secure, path="/api/auth")
    return resp


@router.get("/auth/callback")
def entra_callback(request: Request, code: str = "", state: str = "", error: str = "") -> Response:
    cfg = entra.entra_config()
    if cfg is None or dev_login_enabled():
        raise HTTPException(status_code=404, detail="not_found")
    if error or not code or not state:
        return _login_failed("denied")
    try:
        user_id, email, token_roles, mfa_time = entra.complete(cfg, request.cookies.get(entra.STATE_COOKIE), state, code)
    except entra.EntraError as exc:
        logger.warning("entra sign-in refused: %s", exc.code)
        return _login_failed(exc.code)
    from routes.admin_roles import get_store

    rec = get_store().get(user_id)                         # the in-app registry wins; otherwise the token's app roles
    if rec is not None and not rec.active:
        return _login_failed("forbidden")
    roles = list(rec.roles) if rec else (token_roles or ["viewer"])
    session = create_session(user_id=user_id, email=email, roles=roles, mfa_auth_time=mfa_time or datetime(1970, 1, 1, tzinfo=UTC))
    resp = RedirectResponse("/", status_code=303)
    set_session_cookie(resp, session)
    resp.delete_cookie(entra.STATE_COOKIE, path="/api/auth")
    return resp


@router.post("/auth/dev-login")
def dev_login(body: DevLoginBody, response: Response) -> dict[str, Any]:
    if not dev_login_enabled():
        raise HTTPException(status_code=404, detail="not_found")
    from routes.admin_roles import get_store

    rec = get_store().get(body.user_id)                    # the registry decides roles; the body can never escalate
    if rec is not None and not rec.active:
        raise HTTPException(status_code=403, detail="auth_forbidden_role")
    roles = list(rec.roles) if rec else ["viewer"]
    session = create_session(user_id=body.user_id, email=body.email, roles=roles)
    set_session_cookie(response, session)
    return {
        "user_id": session.user_id,
        "roles": session.roles,
        "mfa_auth_time": session.mfa_auth_time,
        "csrf_token": session.csrf_token,
    }


@router.post("/auth/logout")
def logout(response: Response, session: SessionData = Depends(require_session)) -> dict[str, bool]:
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(session: SessionData = Depends(require_session)) -> dict[str, Any]:
    return {
        "user_id": session.user_id,
        "roles": session.roles,
        "mfa_auth_time": session.mfa_auth_time,
        "csrf_token": session.csrf_token,
    }


# --- Dashboard & Inventory ---

@router.get("/dashboard/risk")
async def get_dashboard_risks(
    warehouse_id: int | None = Query(None),
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: InventoryClient = Depends(get_inventory_client),
) -> list[dict[str, Any]]:
    return await client.get_risks(warehouse_id=warehouse_id, roles=session.roles)


@router.get("/inventory/variants/{variant_id}")
async def get_variant_detail(
    variant_id: int,
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: InventoryClient = Depends(get_inventory_client),
) -> dict[str, Any]:
    return await client.get_variant_detail(variant_id=variant_id, roles=session.roles)


@router.get("/data-quality/import-errors")
async def get_import_errors(
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: InventoryClient = Depends(get_inventory_client),
) -> dict[str, Any]:
    return await client.get_review_items(roles=session.roles)


class ResolveBody(BaseModel):
    decision: str = Field(..., pattern="^(release|ignore)$")


@router.post("/data-quality/import-errors/{error_id}/resolve", status_code=204)
async def resolve_import_error(
    error_id: int,
    body: ResolveBody,
    session: SessionData = Depends(require_roles("buyer", "admin")),
    client: InventoryClient = Depends(get_inventory_client),
) -> None:
    # Map release -> confirm
    mapped_decision = "confirm" if body.decision == "release" else "ignore"
    await client.decide_review(ids=[error_id], decision=mapped_decision, user_id=session.user_id, roles=session.roles)


# --- Suppliers & Costs ---

@router.get("/suppliers")
async def list_suppliers(
    status: str | None = Query(default=None, pattern="^(active|deactivated)$"),
    classification: str | None = Query(default=None, pattern="^(purchasing|non_purchasing|unclassified)$"),
    q: str | None = Query(default=None, max_length=100),
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> list[dict[str, Any]]:
    params = {k: v for k, v in (("status", status), ("classification", classification), ("q", q)) if v}
    return await client.get_suppliers(roles=session.roles, params=params or None)


@router.get("/suppliers/{supplier_id}/terms")
async def get_supplier_terms(
    supplier_id: str,
    as_of: str | None = Query(default=None),
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.get_supplier_terms(supplier_id, as_of=as_of, roles=session.roles)


@router.put("/suppliers/{supplier_id}/terms")
async def update_supplier_terms(
    supplier_id: str,
    terms: dict[str, Any],
    if_match: str | None = Header(default=None),
    session: SessionData = Depends(require_roles("buyer")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.put_supplier_terms(supplier_id=supplier_id, terms=terms, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.get("/product-suppliers/{variant_id}/{supplier_id}/terms")
async def get_override_terms(
    variant_id: int,
    supplier_id: str,
    as_of: str | None = Query(default=None),
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.get_override_terms(variant_id, supplier_id, as_of=as_of, roles=session.roles)


@router.put("/product-suppliers/{variant_id}/{supplier_id}/terms")
async def update_override_terms(
    variant_id: int,
    supplier_id: str,
    body: dict[str, Any],
    if_match: str | None = Header(default=None),
    session: SessionData = Depends(require_roles("buyer")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.put_override_terms(variant_id=variant_id, supplier_id=supplier_id, body=body, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.get("/costs")
async def list_costs(
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> list[dict[str, Any]]:
    return await client.get_costs(roles=session.roles)


@router.post("/costs/import")
async def import_costs(
    payload: dict[str, Any],
    session: SessionData = Depends(require_roles("buyer", "admin")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.import_costs(payload=payload, user_id=session.user_id, roles=session.roles)


@router.get("/cost-writes")
async def list_cost_writes(
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> list[dict[str, Any]]:
    return await client.get_cost_writes(roles=session.roles)


# --- Proposals & Orders ---

@router.get("/proposals")
async def list_proposals(
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> list[dict[str, Any]]:
    return await client.get_proposals(roles=session.roles)


@router.get("/proposals/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.get_proposal(proposal_id=proposal_id, roles=session.roles)


@router.put("/proposals/{proposal_id}/lines/{line_id}")
async def edit_proposal_line(
    proposal_id: str,
    line_id: str,
    payload: dict[str, Any],
    if_match: str | None = Header(default=None),
    session: SessionData = Depends(require_roles("buyer")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.edit_proposal_line(proposal_id=proposal_id, line_id=line_id, payload=payload, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.post("/proposals/{proposal_id}/submit")
async def submit_proposal(
    proposal_id: str,
    if_match: str | None = Header(default=None),
    session: SessionData = Depends(require_roles("buyer")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    if not has_at_least_two_eligible_approvers():            # FR-002: separation of duties needs two people who could approve
        raise HTTPException(status_code=409, detail="approval_fewer_than_two_approvers")
    return await client.submit_proposal(proposal_id=proposal_id, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.post("/proposals/{proposal_id}/approve", dependencies=[Depends(require_fresh_mfa())])
async def approve_proposal(
    proposal_id: str,
    if_match: str | None = Header(default=None),
    session: SessionData = Depends(require_roles("approver")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.approve_proposal(proposal_id=proposal_id, user_id=session.user_id, roles=session.roles, if_match=if_match)


@router.get("/proposals/{proposal_id}/export")
async def export_proposal(
    proposal_id: str,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    supplier_id: str | None = Query(None),
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> Response:
    content = await client.export_proposal(proposal_id=proposal_id, fmt=format, supplier_id=supplier_id, roles=session.roles)
    media_type = "text/csv; charset=utf-8" if format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    filename = f"propuesta_{proposal_id[:8]}.{format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/proposals/{proposal_id}/orders/{supplier_id}/confirm", status_code=201)
async def confirm_order(
    proposal_id: str,
    supplier_id: str,
    payload: dict[str, Any],
    session: SessionData = Depends(require_roles("buyer", "admin")),
    client: ProcurementClient = Depends(get_procurement_client),
) -> dict[str, Any]:
    return await client.confirm_order(proposal_id=proposal_id, supplier_id=supplier_id, payload=payload, user_id=session.user_id, roles=session.roles)


# --- Configuration ---

@router.get("/config/service-levels")
async def get_service_levels(
    session: SessionData = Depends(require_roles("viewer", "buyer", "approver", "admin")),
    client: InventoryClient = Depends(get_inventory_client),
) -> dict[str, Any]:
    return await client.get_service_levels(roles=session.roles)


class LossCutoverPutBody(BaseModel):
    effective_date: str


@router.put("/config/loss-cutover")
def put_loss_cutover(
    body: LossCutoverPutBody,
    session: SessionData = Depends(require_roles("admin")),
) -> dict[str, Any]:
    return {"effective_date": body.effective_date, "updated_by": session.user_id}
