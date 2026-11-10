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
import time
from collections.abc import Callable
from typing import Any

from audit.chain import record_refusal
from fastapi import HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

__all__ = ["FAMILIES", "MAX_JSON_BYTES", "AuditedRoute"]

log = logging.getLogger("procurement.refusals")

FAMILIES = ("/suppliers", "/product-suppliers", "/links")
CHANGE = {"POST", "PUT", "PATCH", "DELETE"}
MAX_JSON_BYTES = 256 * 1024                     # a supplier, a terms version or a link is a few KB; this leaves room for 50 discount tiers of text
_CODE = re.compile(r"[a-z][a-z0-9_]*")
WINDOW_S = 60.0                                 # FR-038: an identical refusal inside this window is stored once
MAX_KEYS = 5000                                 # bound on the in-memory table of recent refusals
_clock = time.monotonic
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


def _sweep(request: Request, keep: tuple[str, str, str, str, int] | None) -> None:
    """Once a minute (or when the table is full): drop closed windows, log the repeats nobody will carry, and report the sign-in failures not stored."""
    state = request.app.state.__dict__
    seen: dict[tuple[str, str, str, str, int], list[float]] = state.setdefault("refusal_seen", {})
    now = _clock()
    if len(seen) < MAX_KEYS and now - state.setdefault("refusal_swept", now) < WINDOW_S:
        return
    state["refusal_swept"] = now
    for old in [k for k, v in seen.items() if now - v[0] >= WINDOW_S and k != keep]:
        if seen[old][1]:
            log.info("refusals skipped in the last minute: skipped %d for %s", int(seen[old][1]), old)
        del seen[old]
    total, reported = getattr(request.app.state, "refusal_unauthenticated", 0), state.get("refusal_unauth_reported", 0)
    if total > reported:                                        # FR-038: the failures counted but never stored become visible
        log.info("refusals not stored in the last minute: %d sign-in failures", total - reported)
        state["refusal_unauth_reported"] = total


def _skip(request: Request, key: tuple[str, str, str, str, int]) -> int | None:
    """FR-038: None when this refusal must be stored (the repeats skipped before it are returned); otherwise it is only counted.

    shortcut: the table lives in this process, so each replica stores at most one entry per key per minute; move it to shared storage if the
    service ever runs more than one replica.
    """
    seen: dict[tuple[str, str, str, str, int], list[float]] = request.app.state.__dict__.setdefault("refusal_seen", {})
    now = _clock()
    entry = seen.get(key)
    if entry is not None and now - entry[0] < WINDOW_S:
        entry[1] += 1
        return None
    repeats = int(entry[1]) if entry is not None else 0
    seen[key] = [now, 0]
    return repeats


def _write(request: Request, action: str, entity: str, entity_id: str, actor: str, code: str, status: int, repeats: int) -> None:
    with _engine(request).begin() as conn:
        record_refusal(conn, actor, action, entity, entity_id, code, status, repeats=repeats)


async def _record(request: Request, path: str, status: int, detail: Any) -> None:
    """Records one refusal. The bookkeeping (FR-038, FR-042) runs here, on the event loop's single thread, so the check-then-store step cannot
    race; only the database write goes to a worker thread, so a burst of refusals never blocks the other requests (FR-039)."""
    try:
        action, entity, entity_id = _target(path, dict(request.path_params))
        actor = str(getattr(request.state, "actor", "unknown"))[:120]
        if status == 401:                                       # no valid sign-in: counted, never stored one by one
            _sweep(request, None)                               # reports the failures up to this one, which belongs to the next minute
            request.app.state.refusal_unauthenticated = getattr(request.app.state, "refusal_unauthenticated", 0) + 1
            return
        code, entity_id = _code(status, detail), entity_id[:60]
        key = (actor, entity, entity_id, code, status)
        _sweep(request, key)
        repeats = _skip(request, key)
        if repeats is not None:
            try:
                await run_in_threadpool(_write, request, action, entity, entity_id, actor, code, status, repeats)
            except Exception:
                request.app.state.refusal_seen.pop(key, None)   # a failed write must not silence the next identical refusal
                raise
    except Exception:
        log.exception("refusal not recorded")


async def _body_within_limit(request: Request) -> bool:
    """FR-040: False when the body is over the limit, whatever its content type; a body without a declared length is read only up to the limit."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit():
        return int(declared) <= MAX_JSON_BYTES
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_JSON_BYTES:
            return False
        chunks.append(chunk)
    request._body = b"".join(chunks)  # the route reads it again from here (Starlette's own cache for body())
    return True


class AuditedRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Any]:
        original = super().get_route_handler()
        path = self.path
        if not (path.startswith(FAMILIES) and self.methods & CHANGE):
            return original

        async def handler(request: Request) -> Response:
            if not await _body_within_limit(request):                 # refused before the body is parsed into the terms
                await _record(request, path, 413, "payload_too_large")
                return JSONResponse({"detail": "payload_too_large"}, status_code=413)
            try:
                response: Response = await original(request)
            except HTTPException as exc:
                await _record(request, path, exc.status_code, exc.detail)
                raise
            except RequestValidationError:
                await _record(request, path, 422, "request_invalid")
                raise
            if 400 <= response.status_code < 500:
                await _record(request, path, response.status_code, _detail_of(response))
            return response

        return handler
