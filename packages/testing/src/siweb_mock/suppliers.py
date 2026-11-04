"""Supplier-cost endpoints of the mock, including the one permitted write.

The PUT mirrors the open verification item V4: the real body/merge semantics are unknown, so the
mock can behave as a *merge* (omitted fields kept) or a *replace* (omitted fields reset), which
is the pitfall a naive writer would hit. The writer must read-modify-write and survive both.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

DEFAULTS_ON_REPLACE = {"is_preferred": False, "lead_time_days": None, "min_order_qty": None, "supplier_reference": None}
WRITABLE = {"purchase_cost_cents", "is_preferred", "lead_time_days", "min_order_qty", "supplier_reference", "currency"}


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
    if not isinstance(body, dict) or "purchase_cost_cents" not in body:
        return JSONResponse({"success": False, "error": "purchase_cost_cents is required"}, status_code=422)
    unknown = set(body) - WRITABLE
    if unknown:
        return JSONResponse({"success": False, "error": f"unknown fields: {sorted(unknown)}"}, status_code=422)
    row = _find(state, product_id, contact_id)
    if row is None:
        if not cfg.allow_create:
            return JSONResponse({"success": False, "error": "supplier link not found"}, status_code=404)
        row = {"contact_id": contact_id, "supplier_name": "Proveedor Sintetico nuevo", "supplier_cif": "X00000000Z",
               "currency": "EUR", **DEFAULTS_ON_REPLACE}
        state.suppliers.setdefault(product_id, []).append(row)
    if cfg.put_semantics == "replace":
        row.update(DEFAULTS_ON_REPLACE)
    row.update({k: v for k, v in body.items() if k in WRITABLE})
    return {"success": True, "data": row}
