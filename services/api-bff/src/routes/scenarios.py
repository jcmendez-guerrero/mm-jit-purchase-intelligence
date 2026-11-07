"""T145: scenario routes. Buyers create and promote; everyone signed in can read and export. The BFF forwards the user and the Idempotency-Key."""

from __future__ import annotations

from typing import Any

from auth.session import SessionData
from clients.procurement import ProcurementClient
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from routes.api import get_procurement_client
from routes.rbac import require_roles

router = APIRouter(prefix="/scenarios")
READ = ("viewer", "buyer", "approver", "admin")


@router.post("", status_code=201)
async def create(body: dict[str, Any], idempotency_key: str | None = Header(default=None), session: SessionData = Depends(require_roles("buyer")),
                 proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    if not idempotency_key:
        raise HTTPException(status_code=422, detail="idempotency_key_required")
    return await proc.forward("POST", "/scenarios", json=body, user_id=session.user_id, roles=session.roles, extra_headers={"Idempotency-Key": idempotency_key})


@router.get("")
async def listing(session: SessionData = Depends(require_roles(*READ)), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("GET", "/scenarios", user_id=session.user_id, roles=session.roles)


@router.get("/{sid}")
async def read(sid: str, session: SessionData = Depends(require_roles(*READ)), proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("GET", f"/scenarios/{sid}", user_id=session.user_id, roles=session.roles)


@router.post("/{sid}/promote", status_code=201)
async def promote(sid: str, body: dict[str, Any] | None = None, session: SessionData = Depends(require_roles("buyer")),
                  proc: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await proc.forward("POST", f"/scenarios/{sid}/promote", json=body or {}, user_id=session.user_id, roles=session.roles)


@router.get("/{sid}/export")
async def export(sid: str, format: str = Query(pattern="^(csv|xlsx)$"), session: SessionData = Depends(require_roles(*READ)),
                 proc: ProcurementClient = Depends(get_procurement_client)) -> Response:
    res = await proc.forward_raw("GET", f"/scenarios/{sid}/export", params={"format": format}, user_id=session.user_id, roles=session.roles)
    return Response(res.content, media_type=res.headers.get("content-type"), headers={k: v for k, v in res.headers.items() if k.lower() == "content-disposition"})
