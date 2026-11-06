"""api-bff service entrypoint (T109, T110, T111, T137)."""

import re

import httpx
from auth.identity import current_identity
from auth.session import get_current_session
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mmi_common.service import create_service_app
from routes.admin_roles import router as admin_roles_router
from routes.api import router as api_router

# In api-bff, user session cookies are used for the frontend API.
# Service skeleton provides /healthz, /readyz.
app: FastAPI = create_service_app("api-bff", validator=lambda: None)



@app.middleware("http")
async def bind_identity(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Make the verified session visible to the downstream clients for the duration of this request only."""
    token = current_identity.set(get_current_session(request))
    try:
        return await call_next(request)
    finally:
        current_identity.reset(token)


CODE = re.compile(r"[a-z][a-z0-9_:]{0,79}")


@app.exception_handler(httpx.HTTPStatusError)
async def downstream_status(_: Request, exc: httpx.HTTPStatusError) -> JSONResponse:
    """A downstream refusal keeps its status and its stable code; anything that is not a plain code is replaced, never echoed."""
    status = exc.response.status_code
    if 400 <= status < 500:
        try:
            detail = exc.response.json().get("detail")
        except Exception:
            detail = None
        body: dict[str, object] = {"detail": detail if isinstance(detail, str) and CODE.fullmatch(detail) else "downstream_refused"}
        try:
            current = exc.response.json().get("current_version")
        except Exception:
            current = None
        if status == 412 and isinstance(current, int) and not isinstance(current, bool):
            body["current_version"] = current              # a stale editor learns which version is in force
        return JSONResponse(body, status_code=status)
    return JSONResponse({"detail": "downstream_unavailable"}, status_code=502)


@app.exception_handler(httpx.TransportError)
async def downstream_unreachable(_: Request, exc: httpx.TransportError) -> JSONResponse:
    return JSONResponse({"detail": "downstream_unavailable"}, status_code=502)


@app.exception_handler(RuntimeError)
async def identity_unavailable(_: Request, exc: RuntimeError) -> JSONResponse:
    if "identity" in str(exc):
        return JSONResponse({"detail": "authentication_unavailable"}, status_code=503)
    raise exc


# Mount frontend-facing endpoints under /api per bff-api.openapi.yaml
app.include_router(api_router, prefix="/api")
app.include_router(admin_roles_router, prefix="/api")
