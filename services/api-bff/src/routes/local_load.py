"""T037: BFF routes of the local export loader. Mounted only when MMI_LOCAL_LOADER=1 and the environment is not prod/staging (FR-023).

Buyers and admins only. The BFF checks type and size, forwards the file in memory to the loader as its own service identity and
returns the loader's counts or stable refusal code. Nothing about the file's content is stored or audited here: only who loaded
what kind of file and the counts.
"""

from __future__ import annotations

import os
import re
import time
from collections import OrderedDict
from collections.abc import Mapping
from typing import Any

import httpx
from auth.session import SessionData
from clients.loader import LoaderClient
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from routes.admin_roles import get_store
from routes.rbac import require_roles
from upload_settings import load_limits

router = APIRouter(prefix="/local-load", tags=["local-load"])
KINDS = {"suppliers", "inventory", "movements"}
ID = re.compile(r"^[A-Za-z0-9-]{3,64}$")
IDEMPOTENCY_TTL_S = 900
_idempotent: OrderedDict[str, tuple[float, Any]] = OrderedDict()


def enabled(env: Mapping[str, str] | None = None) -> bool:
    e = os.environ if env is None else env
    return e.get("MMI_LOCAL_LOADER") == "1" and e.get("MMI_ENV", "") not in {"prod", "staging"}


def get_loader_client() -> LoaderClient:
    return LoaderClient()


def _kind(kind: str) -> str:
    if kind not in KINDS:
        raise HTTPException(404, "local_load_unknown_kind")
    return kind


async def _read(file: UploadFile) -> tuple[str, bytes, str]:
    limits = load_limits()
    name = file.filename or ""
    if not name.lower().endswith(limits.allowed_extensions):
        raise HTTPException(415, "local_load_type_not_allowed")
    data = await file.read(limits.max_bytes + 1)
    if len(data) > limits.max_bytes:
        raise HTTPException(413, "local_load_file_too_large")
    return name, data, file.content_type or "application/octet-stream"


def _answer(status: int, body: Any) -> Any:
    if status < 400:
        return body
    out: dict[str, Any] = {"detail": body.get("code", "downstream_refused") if isinstance(body, dict) else "downstream_refused"}
    if isinstance(body, dict) and body.get("missing"):
        out["missing"], out["unexpected"] = body["missing"], body.get("unexpected", [])
    return JSONResponse(out, status_code=status)


async def _call(loader: LoaderClient, method: str, path: str, **kw: Any) -> Any:
    try:
        status, body = await loader.request(method, path, **kw)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "local_load_unreachable") from exc
    return _answer(status, body)


@router.get("/capability")
async def capability(_s: SessionData = Depends(require_roles("buyer", "admin")), loader: LoaderClient = Depends(get_loader_client)) -> dict[str, bool]:
    try:
        return {"enabled": await loader.health()}
    except httpx.HTTPError:
        return {"enabled": False}


@router.post("/{kind}/check")
async def check(kind: str, file: UploadFile = File(...), _s: SessionData = Depends(require_roles("buyer", "admin")),
                loader: LoaderClient = Depends(get_loader_client)) -> Any:
    name, data, ctype = await _read(file)
    return await _call(loader, "POST", f"/check/{_kind(kind)}", files={"file": (name, data, ctype)})


@router.post("/{kind}")
async def load(kind: str, file: UploadFile = File(...), acknowledge_interpretation: bool = Query(False),
               idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
               session: SessionData = Depends(require_roles("buyer", "admin")), loader: LoaderClient = Depends(get_loader_client)) -> Any:
    _kind(kind)
    if not idempotency_key or not ID.match(idempotency_key):
        raise HTTPException(400, "idempotency_key_required")
    now = time.monotonic()
    for k in [k for k, (t, _) in _idempotent.items() if now - t > IDEMPOTENCY_TTL_S]:
        del _idempotent[k]
    cache_key = f"{session.user_id}|{kind}|{idempotency_key}"
    if cache_key in _idempotent:
        return _idempotent[cache_key][1]
    name, data, ctype = await _read(file)
    result = await _call(loader, "POST", f"/load/{kind}", params={"acknowledge_interpretation": str(acknowledge_interpretation).lower()},
                         files={"file": (name, data, ctype)})
    if isinstance(result, dict):
        get_store().record_action(session.user_id, "local_load.load", kind, after={k: result.get(k) for k in
                                  ("rows", "loaded", "updated", "unchanged", "quarantined", "excluded", "services", "differences")})
        _idempotent[cache_key] = (now, result)
    return result


@router.get("/runs")
async def runs(_s: SessionData = Depends(require_roles("buyer", "admin")), loader: LoaderClient = Depends(get_loader_client)) -> Any:
    return await _call(loader, "GET", "/runs")


@router.get("/review")
async def review(_s: SessionData = Depends(require_roles("buyer", "admin")), loader: LoaderClient = Depends(get_loader_client)) -> Any:
    return await _call(loader, "GET", "/review")


@router.get("/differences")
async def differences(_s: SessionData = Depends(require_roles("buyer", "admin")), loader: LoaderClient = Depends(get_loader_client)) -> Any:
    return await _call(loader, "GET", "/differences")


@router.post("/differences/{diff_id}/{decision}", status_code=204)
async def decide(diff_id: str, decision: str, session: SessionData = Depends(require_roles("buyer", "admin")),
                 loader: LoaderClient = Depends(get_loader_client)) -> Response:
    if decision not in {"accept", "ignore"}:
        raise HTTPException(404, "local_load_unknown_decision")
    if not ID.match(diff_id):
        raise HTTPException(422, "request_invalid")
    result = await _call(loader, "POST", f"/differences/{diff_id}/{decision}")
    if isinstance(result, JSONResponse):
        return result
    get_store().record_action(session.user_id, f"local_load.difference_{decision}", diff_id)
    return Response(status_code=204)
