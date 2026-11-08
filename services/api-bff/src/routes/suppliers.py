"""T052: supplier management through the BFF (contracts/suppliers-api.md). It holds no rule: it checks roles, validates path shapes,
forwards to procurement-service as the signed-in user and lets the owning service answer with its stable codes.

Buyers and admins write; every signed-in role reads. Terms keep their own, stricter, buyer-only routes in ``routes.api``.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from auth.session import SessionData
from clients.procurement import ProcurementClient
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile
from routes.api import get_procurement_client
from routes.rbac import require_roles
from upload_settings import load_limits

router = APIRouter(tags=["suppliers"])
READERS = ("viewer", "buyer", "approver", "admin")
SKU_MAX = 60
ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _check_id(value: str) -> str:
    if not ID.match(value):
        raise HTTPException(422, "request_invalid")
    return value


def _sku(value: str) -> str:
    if not value.strip() or len(value) > SKU_MAX or any(ord(c) < 32 for c in value):
        raise HTTPException(422, "request_invalid")
    return quote(value, safe="")


async def _fwd(client: ProcurementClient, session: SessionData, method: str, path: str, **kw: Any) -> Any:
    return await client.forward(method, path, user_id=session.user_id, roles=session.roles, **kw)


# --- review items first: a literal path must win over /suppliers/{supplier_id}
@router.get("/suppliers/review-items")
async def review_items(status: str = Query(default="open"), session: SessionData = Depends(require_roles(*READERS)),
                       client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await _fwd(client, session, "GET", "/suppliers/review-items", params={"status": status})


@router.post("/suppliers/review-items/{item_id}/resolve", status_code=204)
async def resolve(item_id: str, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer", "admin")),
                  client: ProcurementClient = Depends(get_procurement_client)) -> Response:
    await _fwd(client, session, "POST", f"/suppliers/review-items/{_check_id(item_id)}/resolve", json=body)
    return Response(status_code=204)


@router.post("/suppliers", status_code=201)
async def create(body: dict[str, Any], confirm_duplicate: bool = Query(default=False), session: SessionData = Depends(require_roles("buyer", "admin")),
                 client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await _fwd(client, session, "POST", "/suppliers", json=body, params={"confirm_duplicate": "true"} if confirm_duplicate else None)


@router.get("/suppliers/{supplier_id}")
async def detail(supplier_id: str, session: SessionData = Depends(require_roles(*READERS)), client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await _fwd(client, session, "GET", f"/suppliers/{quote(supplier_id, safe='')}")


@router.patch("/suppliers/{supplier_id}")
async def patch(supplier_id: str, body: dict[str, Any], confirm_duplicate: bool = Query(default=False), if_match: str | None = Header(default=None),
                session: SessionData = Depends(require_roles("buyer", "admin")), client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    if if_match is None:
        raise HTTPException(428, "revision_required")
    return await _fwd(client, session, "PATCH", f"/suppliers/{quote(supplier_id, safe='')}", json=body, if_match=if_match,
                      params={"confirm_duplicate": "true"} if confirm_duplicate else None)


@router.post("/suppliers/{supplier_id}/deactivate")
async def deactivate(supplier_id: str, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer", "admin")),
                     client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await _fwd(client, session, "POST", f"/suppliers/{quote(supplier_id, safe='')}/deactivate", json=body)


@router.post("/suppliers/{supplier_id}/reactivate")
async def reactivate(supplier_id: str, session: SessionData = Depends(require_roles("buyer", "admin")),
                     client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await _fwd(client, session, "POST", f"/suppliers/{quote(supplier_id, safe='')}/reactivate")


@router.post("/suppliers/{supplier_id}/merge")
async def merge(supplier_id: str, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer", "admin")),
                client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await _fwd(client, session, "POST", f"/suppliers/{quote(supplier_id, safe='')}/merge", json=body)


@router.get("/suppliers/{supplier_id}/links")
async def links(supplier_id: str, session: SessionData = Depends(require_roles(*READERS)), client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await _fwd(client, session, "GET", f"/suppliers/{quote(supplier_id, safe='')}/links")


@router.put("/suppliers/{supplier_id}/links/{sku:path}")
async def put_link(supplier_id: str, sku: str, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer", "admin")),
                   client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await _fwd(client, session, "PUT", f"/suppliers/{quote(supplier_id, safe='')}/links/{_sku(sku)}", json=body)


@router.delete("/suppliers/{supplier_id}/links/{sku:path}", status_code=204)
async def delete_link(supplier_id: str, sku: str, session: SessionData = Depends(require_roles("buyer", "admin")),
                      client: ProcurementClient = Depends(get_procurement_client)) -> Response:
    await _fwd(client, session, "DELETE", f"/suppliers/{quote(supplier_id, safe='')}/links/{_sku(sku)}")
    return Response(status_code=204)


@router.post("/suppliers/{supplier_id}/links/bulk/preview")
async def bulk_preview(supplier_id: str, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer", "admin")),
                       client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await _fwd(client, session, "POST", f"/suppliers/{quote(supplier_id, safe='')}/links/bulk/preview", json=body)


@router.post("/suppliers/{supplier_id}/links/bulk/apply")
async def bulk_apply(supplier_id: str, body: dict[str, Any], session: SessionData = Depends(require_roles("buyer", "admin")),
                     client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    return await _fwd(client, session, "POST", f"/suppliers/{quote(supplier_id, safe='')}/links/bulk/apply", json=body)


@router.post("/links/bulk/file")
async def bulk_file(file: UploadFile = File(...), session: SessionData = Depends(require_roles("buyer", "admin")),
                    client: ProcurementClient = Depends(get_procurement_client)) -> Any:
    limits = load_limits()
    name = file.filename or ""
    if not name.lower().endswith((".csv", ".txt")):
        raise HTTPException(415, "import_type_not_allowed")
    data = await file.read(limits.max_bytes + 1)
    if len(data) > limits.max_bytes:
        raise HTTPException(413, "import_file_too_large")
    res = await client.forward_raw("POST", "/links/bulk/file", files={"file": (name, data, "text/csv")}, user_id=session.user_id, roles=session.roles)
    return res.json()
