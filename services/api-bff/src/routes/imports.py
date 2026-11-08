"""T106 / T116: predictive seed import routes.

The BFF enforces session, CSRF (the existing middleware), role, the declared and the actual size cap, and the name/type allow-list
before anything is sent on. It streams the bytes to forecast-service, which re-checks the file itself (signature, macros, decompression).
"""

from __future__ import annotations

from typing import Any

from auth.session import SessionData
from clients.forecast import ForecastClient
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from routes.policies import get_forecast_client
from routes.rbac import require_roles
from upload_settings import load_limits

router = APIRouter(prefix="/imports")
EDIT = ("buyer", "admin")
READ = ("viewer", "buyer", "approver", "admin")


@router.get("/template")
async def template(format: str = Query(default="csv", pattern="^(csv|xlsx)$"), session: SessionData = Depends(require_roles(*READ)),
                   fc: ForecastClient = Depends(get_forecast_client)) -> Response:
    res = await fc.forward_raw("GET", "/imports/template", params={"format": format}, user_id=session.user_id, roles=session.roles)
    return Response(res.content, media_type=res.headers.get("content-type"), headers={"Content-Disposition": res.headers.get("content-disposition", "attachment")})


@router.get("")
async def list_datasets(session: SessionData = Depends(require_roles(*READ)), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    return await fc.forward("GET", "/imports", user_id=session.user_id, roles=session.roles)


@router.get("/mappings")
async def mappings(session: SessionData = Depends(require_roles(*READ)), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    return await fc.forward("GET", "/imports/mappings", user_id=session.user_id, roles=session.roles)


@router.post("/mappings", status_code=201)
async def save_mapping(body: dict[str, Any], session: SessionData = Depends(require_roles(*EDIT)), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    return await fc.forward("POST", "/imports/mappings", json=body, user_id=session.user_id, roles=session.roles)


@router.post("", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), name: str = Form(default=""), session: SessionData = Depends(require_roles(*EDIT)),
                 fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    limits = load_limits()
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limits.max_bytes + 64 * 1024:       # the multipart envelope adds a little
        raise HTTPException(status_code=413, detail="import_file_too_large")
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(limits.allowed_extensions):
        raise HTTPException(status_code=415, detail="import_type_not_allowed")
    data = bytearray()
    while chunk := await file.read(64 * 1024):                                                              # read in chunks and stop at the cap
        data += chunk
        if len(data) > limits.max_bytes:
            raise HTTPException(status_code=413, detail="import_file_too_large")
    res = await fc.forward_raw("POST", "/imports", files={"file": (filename, bytes(data), file.content_type or "application/octet-stream")}, data={"name": name[:200]},
                               user_id=session.user_id, roles=session.roles)
    return res.json()


@router.post("/rollback")
async def rollback(session: SessionData = Depends(require_roles(*EDIT)), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    return await fc.forward("POST", "/imports/rollback", json={}, user_id=session.user_id, roles=session.roles)


@router.get("/jobs")
async def jobs(session: SessionData = Depends(require_roles(*READ)), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    return await fc.forward("GET", "/imports/jobs", user_id=session.user_id, roles=session.roles)


@router.post("/{dataset_id}/validate")
async def validate(dataset_id: str, body: dict[str, Any], response: Response, session: SessionData = Depends(require_roles(*EDIT)),
                   fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    """200 when validated now; 202 when a large file was sent to the background (the status section shows it)."""
    res = await fc.forward_raw("POST", f"/imports/{dataset_id}/validate", data=None, user_id=session.user_id, roles=session.roles, json_body=body)
    response.status_code = res.status_code
    return res.json()


@router.get("/{dataset_id}/quarantine")
async def quarantine(dataset_id: str, format: str = Query(default="json", pattern="^(json|csv|xlsx)$"), session: SessionData = Depends(require_roles(*READ)),
                     fc: ForecastClient = Depends(get_forecast_client)) -> Response:
    res = await fc.forward_raw("GET", f"/imports/{dataset_id}/quarantine", params={"format": format}, user_id=session.user_id, roles=session.roles)
    return Response(res.content, media_type=res.headers.get("content-type"), headers={k: v for k, v in res.headers.items() if k.lower() == "content-disposition"})


@router.post("/{dataset_id}/dry-run")
async def dry_run(dataset_id: str, session: SessionData = Depends(require_roles(*EDIT)), fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    return await fc.forward("POST", f"/imports/{dataset_id}/dry-run", json={}, user_id=session.user_id, roles=session.roles)


@router.post("/{dataset_id}/activate")
async def activate(dataset_id: str, body: dict[str, Any] | None = None, session: SessionData = Depends(require_roles(*EDIT)),
                   fc: ForecastClient = Depends(get_forecast_client)) -> Any:
    return await fc.forward("POST", f"/imports/{dataset_id}/activate", json=body or {}, user_id=session.user_id, roles=session.roles)


@router.post("/{dataset_id}/reject", status_code=204)
async def reject(dataset_id: str, session: SessionData = Depends(require_roles(*EDIT)), fc: ForecastClient = Depends(get_forecast_client)) -> Response:
    await fc.forward("POST", f"/imports/{dataset_id}/reject", json={}, user_id=session.user_id, roles=session.roles)
    return Response(status_code=204)
