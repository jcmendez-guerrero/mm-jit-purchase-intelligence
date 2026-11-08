"""T036: the loader's local HTTP app (compose override only). Files are processed in memory and never written to disk.

Every call (except ``/healthz``) needs a token for audience ``api://mmi-local-loader`` from the BFF or the local command. The app
refuses to start outside ``MMI_ENV=dev`` and talks only to local services.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from mmi_common.auth import AuthError

from . import guards
from .auth import LoaderAuth, validator_from_env
from .cli import DEFAULT_CONNECTOR, default_state_dir, http_push, http_sync
from .push_costs import http_push_costs
from .service import LoaderService
from .to_procurement import http_push_links, http_push_suppliers
from .validate_file import LoaderFileError, load_limits

KINDS = {"suppliers", "inventory", "movements"}
STATUS = {
    "local_load_file_too_large": 413, "local_load_too_many_rows": 413, "local_load_type_not_allowed": 415, "local_load_macros_or_links": 415,
    "local_load_signature_mismatch": 422, "local_load_interpretation_not_acknowledged": 409, "local_load_inventory_required": 409,
    "local_load_unknown_difference": 404, "local_load_kind_not_available": 400, "local_load_platform_unreachable": 502,
}


def create_app(service: LoaderService | None = None, gate: LoaderAuth | None = None, sync: Callable[[], dict[str, Any]] | None = None) -> FastAPI:
    guards.check_environment()
    if service is None:
        mock = guards.check_local_url(os.environ.get("MMI_SIWEB_MOCK_URL", "http://localhost:8089"))
        costs_url = os.environ.get("MMI_PROCUREMENT_URL")
        service = LoaderService(default_state_dir(), http_push(mock), push_costs=http_push_costs(costs_url) if costs_url else None,
                                push_suppliers=http_push_suppliers(costs_url) if costs_url else None, push_links=http_push_links(costs_url) if costs_url else None)
        sync = sync or http_sync(guards.check_local_url(os.environ.get("MMI_CONNECTOR_URL", DEFAULT_CONNECTOR)))
    gate = gate or LoaderAuth(validator_from_env())
    app = FastAPI(title="export loader (local only)")
    limits = load_limits()
    last_sync: dict[str, Any] = {}

    def principal(authorization: str | None = Header(default=None)) -> None:
        try:
            gate.check(authorization)
        except AuthError as exc:
            raise HTTPException(exc.status, detail="no autorizado") from exc

    @app.exception_handler(LoaderFileError)
    async def file_error(_request: Any, exc: LoaderFileError) -> JSONResponse:
        body: dict[str, Any] = {"code": exc.code, "message": str(exc)}
        if exc.missing:
            body["missing"], body["unexpected"] = exc.missing, exc.unexpected
        return JSONResponse(body, status_code=STATUS.get(exc.code, 400))

    async def read_upload(file: UploadFile) -> bytes:
        data = await file.read(limits.max_bytes + 1)         # never buffers more than the limit allows
        return data

    def kind_of(kind: str) -> str:
        if kind not in KINDS:
            raise HTTPException(400, detail="tipo de exportación no admitido")
        return kind

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/check/{kind}", dependencies=[Depends(principal)])
    async def check(kind: str, file: UploadFile = File(...)) -> dict[str, Any]:
        return service.check(kind_of(kind), file.filename or "", await read_upload(file))

    @app.post("/load/{kind}", dependencies=[Depends(principal)])
    async def load(kind: str, file: UploadFile = File(...), acknowledge_interpretation: bool = Query(False)) -> dict[str, Any]:
        result = service.load(kind_of(kind), file.filename or "", await read_upload(file), acknowledge_interpretation=acknowledge_interpretation)
        if sync is not None:
            try:
                last_sync.update(sync())
            except Exception as exc:  # the load itself succeeded; the screen shows the sync state from /state
                last_sync.update({"ok": False, "error": type(exc).__name__})
        return result

    @app.get("/runs", dependencies=[Depends(principal)])
    def runs() -> list[dict[str, Any]]:
        return service.runs()

    @app.get("/review", dependencies=[Depends(principal)])
    def review() -> list[dict[str, Any]]:
        return service.review_items()

    @app.get("/differences", dependencies=[Depends(principal)])
    def differences() -> list[dict[str, Any]]:
        return service.differences()

    @app.post("/differences/{diff_id}/accept", status_code=204, dependencies=[Depends(principal)])
    def accept(diff_id: str) -> Response:
        service.resolve_difference(diff_id, "accept")
        return Response(status_code=204)

    @app.post("/differences/{diff_id}/ignore", status_code=204, dependencies=[Depends(principal)])
    def ignore(diff_id: str) -> Response:
        service.resolve_difference(diff_id, "ignore")
        return Response(status_code=204)

    @app.get("/state", dependencies=[Depends(principal)])
    def state() -> dict[str, Any]:
        return {"runs": len(service.runs()), "open_differences": sum(1 for d in service.differences() if d["status"] == "open"),
                "last_sync_ok": last_sync.get("ok")}

    @app.delete("/state", status_code=204, dependencies=[Depends(principal)])
    def wipe() -> Response:
        service.wipe()
        return Response(status_code=204)

    return app
