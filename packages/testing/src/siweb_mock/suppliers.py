"""Supplier-cost endpoints of the mock, including the one permitted write.

Behaviour verified against the real API on a test product (research V4, 2026-11-04/05): the PUT upserts (a missing link
is created), merges omitted fields, ignores ``lead_time_days``/``min_order_qty`` and unknown fields, accepts fractional
cents and rejects a negative or non-numeric cost with 400. ``put_semantics="replace"`` and ``allow_create=False``
remain available to stress a writer against the pitfalls a naive client could hit.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

WRITABLE = {"purchase_cost_cents", "is_preferred", "supplier_reference"}   # lead time and minimum order are read-only here


def _state(request: Request):
    return request.app.state.mock


def _find(state, product_id: int, contact_id: int) -> dict[str, Any] | None:
    return next((r for r in state.suppliers.get(product_id, []) if r["contact_id"] == contact_id), None)


@router.get("/api/public/inventory/products/{product_id}/suppliers")
def list_suppliers(product_id: int, request: Request):
    state = _state(request)
    return {"success": True, "data": state.suppliers.get(product_id, [])}


@router.put("/api/public/inventory/products/{product_id}/suppliers/{contact_id}")
async def put_supplier(product_id: int, contact_id: int, request: Request):
    state = _state(request)
    cfg = state.config
    if cfg.fail_next_puts > 0:
        cfg.fail_next_puts -= 1
        return JSONResponse({"success": False, "error": "injected failure"}, status_code=cfg.fail_status)
    body = await request.json()
    cost = body.get("purchase_cost_cents") if isinstance(body, dict) else None
    if isinstance(cost, bool) or not isinstance(cost, int | float) or cost < 0:
        return JSONResponse({"success": False, "message": "purchase_cost_cents debe ser un número mayor o igual que 0"}, status_code=400)
    row = _find(state, product_id, contact_id)
    if row is None:
        if not cfg.allow_create:
            return JSONResponse({"success": False, "error": "supplier link not found"}, status_code=404)
        row = {"contact_id": contact_id, "supplier_name": "Proveedor Sintetico nuevo", "supplier_cif": "X00000000Z",
               "currency": "EUR", "supplier_reference": None, "lead_time_days": None, "min_order_qty": None, "is_preferred": False}
        state.suppliers.setdefault(product_id, []).append(row)
    if cfg.put_semantics == "replace":
        row.update({"is_preferred": False, "supplier_reference": None})
    row.update({k: v for k, v in body.items() if k in WRITABLE})
    return {"success": True, "data": row}
