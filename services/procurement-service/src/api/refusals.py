"""MMI-6 (FR-028, SC-007): every refused change to a supplier, its terms, an override, a link or a bulk assignment is recorded.

``AuditedRoute`` wraps only change requests (POST, PUT, PATCH, DELETE) on the supplier families. A 4xx answer, a request the schema rejects, an
HTTPException from a role check, or a body that is too large leaves one ``terms.refused`` / ``supplier.refused`` / ``link.refused`` entry in the
hash-chained audit trail with the actor, the target, the stable error code and the status: never the request body. The entry is written in its
own transaction, because the request's own transaction is rolled back when it is refused. A failure to record is logged and never changes the answer.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any

from audit.chain import record_refusal
from fastapi import HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

__all__ = ["FAMILIES", "MAX_JSON_BYTES", "AuditedRoute"]

log = logging.getLogger("procurement.refusals")

FAMILIES = ("/suppliers", "/product-suppliers", "/links")
CHANGE = {"POST", "PUT", "PATCH", "DELETE"}
MAX_JSON_BYTES = 256 * 1024                     # a supplier, a terms version or a link is a few KB; this leaves room for 50 discount tiers of text
_CODE = re.compile(r"[a-z][a-z0-9_]*")
_BY_STATUS = {401: "unauthenticated", 403: "auth_forbidden_role", 404: "not_found", 413: "payload_too_large", 422: "request_invalid"}


def _target(path: str, params: dict[str, Any]) -> tuple[str, str, str]:
    """(action, entity, entity id) of the thing a request was aimed at, from its route path and path parameters."""
    supplier = str(params.get("supplier_id", ""))
    if path.startswith("/product-suppliers"):
        return "terms.refused", "product_supplier_terms", f"{params.get('variant_id')}:{supplier}"
    if "/terms" in path:
        return "terms.refused", "supplier_terms", supplier or "-"
    if "/links" in path:
        sku = str(params.get("sku", ""))
        return "link.refused", "supplier_link", (f"{supplier}:{sku}" if sku else supplier) or "-"
    return "supplier.refused", "supplier", supplier or str(params.get("item_id", "")) or "-"


def _code(status: int, detail: Any) -> str:
    if isinstance(detail, str):
        if status == 403 and detail == "forbidden":               # the shared role check says "forbidden"; the catalogue code is auth_forbidden_role
            return "auth_forbidden_role"
        if _CODE.fullmatch(detail):
            return detail
    return _BY_STATUS.get(status, "refused")


def _detail_of(response: Response) -> Any:
    try:
        return json.loads(bytes(response.body)).get("detail")
    except (ValueError, AttributeError, TypeError):
        return None


def _engine(request: Request) -> Any:
    from api.costs import get_engine  # late: costs.py imports this module for its route class

    return request.app.dependency_overrides.get(get_engine, get_engine)()


def _record(request: Request, path: str, status: int, detail: Any) -> None:
    try:
        action, entity, entity_id = _target(path, dict(request.path_params))
        actor = str(getattr(request.state, "actor", "unknown"))[:120]
        with _engine(request).begin() as conn:
            record_refusal(conn, actor, action, entity, entity_id[:60], _code(status, detail), status)
    except Exception:
        log.exception("refusal not recorded")


class AuditedRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Any]:
        original = super().get_route_handler()
        path = self.path
        if not (path.startswith(FAMILIES) and self.methods & CHANGE):
            return original

        async def handler(request: Request) -> Response:
            if request.headers.get("content-type", "").startswith("application/json"):
                declared = request.headers.get("content-length", "")
                size = int(declared) if declared.isdigit() else len(await request.body())
                if size > MAX_JSON_BYTES:                       # refused before the body is parsed into the terms
                    _record(request, path, 413, "payload_too_large")
                    return JSONResponse({"detail": "payload_too_large"}, status_code=413)
            try:
                response: Response = await original(request)
            except HTTPException as exc:
                _record(request, path, exc.status_code, exc.detail)
                raise
            except RequestValidationError:
                _record(request, path, 422, "request_invalid")
                raise
            if 400 <= response.status_code < 500:
                _record(request, path, response.status_code, _detail_of(response))
            return response

        return handler
