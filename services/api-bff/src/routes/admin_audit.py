"""Admin audit viewer (feature 010, US2): filter, verify and export the BFF hash chain. Admin only; export needs fresh MFA and is itself audited."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

from auth.session import SessionData
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from routes.admin_roles import get_store
from routes.rbac import require_fresh_mfa, require_roles

router = APIRouter(prefix="/admin/audit", tags=["admin"])
EXPORT_CAP = 10_000
FIELDS = ("id", "ts", "actor", "action", "entity", "entity_id", "outcome", "reason_code")


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(422, "request_invalid") from exc
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _filters(actor: str | None, action: str | None, outcome: str | None, ts_from: str | None, ts_to: str | None) -> dict[str, Any]:
    if outcome not in (None, "allowed", "refused"):
        raise HTTPException(422, "request_invalid")
    return {"actor": actor, "action": action, "outcome": outcome, "ts_from": _when(ts_from), "ts_to": _when(ts_to)}


@router.get("")
def list_audit(actor: str | None = Query(None, max_length=120), action: str | None = Query(None, max_length=40), outcome: str | None = None,
               from_: str | None = Query(None, alias="from", max_length=40), to: str | None = Query(None, max_length=40),
               cursor: int | None = Query(None, ge=1), limit: int = Query(50, ge=1, le=200),
               _: SessionData = Depends(require_roles("admin"))) -> dict[str, Any]:
    items, nxt = get_store().audit_page(**_filters(actor, action, outcome, from_, to), cursor=cursor, limit=limit)
    return {"items": items, "next_cursor": str(nxt) if nxt else None}


@router.get("/verify")
def verify(_: SessionData = Depends(require_roles("admin"))) -> dict[str, Any]:
    check = get_store().verify_audit()
    return {"ok": check.ok, "checked": check.checked, "first_broken_id": check.broken_at}


@router.get("/export")
def export(actor: str | None = Query(None, max_length=120), action: str | None = Query(None, max_length=40), outcome: str | None = None,
           from_: str | None = Query(None, alias="from", max_length=40), to: str | None = Query(None, max_length=40),
           session: SessionData = Depends(require_roles("admin")), _fresh: SessionData = Depends(require_fresh_mfa())) -> Response:
    store = get_store()
    flt = _filters(actor, action, outcome, from_, to)
    items: list[dict[str, Any]] = []
    cursor = None
    while len(items) <= EXPORT_CAP:
        page, cursor = store.audit_page(**flt, cursor=cursor, limit=200)
        items.extend(page)
        if cursor is None:
            break
    truncated = len(items) > EXPORT_CAP
    items = items[:EXPORT_CAP]
    store.record_action(session.user_id, "audit.exported", "audit", after={"rows": len(items), "truncated": truncated})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for row in items:
        w.writerow({k: ("'" + str(v) if isinstance(v, str) and v[:1] in "=+-@" else v) for k, v in row.items()})   # no spreadsheet formula injection
    return Response(buf.getvalue(), media_type="text/csv", headers={"X-Export-Truncated": "true" if truncated else "false",
                                                                     "Content-Disposition": 'attachment; filename="audit.csv"'})
