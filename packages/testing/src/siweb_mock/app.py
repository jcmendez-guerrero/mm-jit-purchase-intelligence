"""Synthetic Siweb360 mock. Reproduces the documented behaviours and the awkward ones.

Pagination shapes (plan 2, row 18): inventory -> ``pagination{page,limit,total,pages}``;
purchases -> top-level ``page/limit/totalPages``; tickets -> ``total`` only.
Timestamps are offset-less. Movements are served newest first and can shift mid-run.
Every request is logged so tests can assert exactly what a client sent.
"""

from __future__ import annotations

import math
import os
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from generator import Dataset, generate

from . import suppliers
from .state import MockConfig, MockState


def create_app(data: Dataset | None = None, config: MockConfig | None = None) -> FastAPI:
    state = MockState(data or generate(), config or MockConfig())
    app = FastAPI(title="Siweb360 mock (synthetic)")
    app.state.mock = state
    app.include_router(suppliers.router)

    @app.middleware("http")
    async def gate(request: Request, call_next):
        s: MockState = app.state.mock
        path = request.url.path
        if path.startswith("/__mock__"):
            return await call_next(request)
        s.total_requests += 1
        cfg = s.config
        status = None
        if request.headers.get("authorization") != f"Bearer {cfg.token}":
            status = 401
        elif cfg.unauthorized_after is not None and s.total_requests > cfg.unauthorized_after:
            status = 401
        elif cfg.rate_limit_per_hour is not None:
            if time.time() - s.window_started > 3600:
                s.window_started, s.total_requests = time.time(), 1
            if s.total_requests > cfg.rate_limit_per_hour:
                status = 429
        if status is not None:
            headers = {"Retry-After": "60"} if status == 429 and cfg.send_retry_after else {}
            response: Any = JSONResponse({"success": False, "error": "unauthorized" if status == 401 else "rate limited"}, status_code=status, headers=headers)
        else:
            response = await call_next(request)
        s.request_log.append({"method": request.method, "path": path, "query": dict(request.query_params), "status": response.status_code})
        return response

    def st() -> MockState:
        return app.state.mock

    def inv_page(rows: list[dict[str, Any]], page: int, limit: int) -> dict[str, Any]:
        total = len(rows)
        start = (page - 1) * limit
        return {"success": True, "data": rows[start:start + limit],
                "pagination": {"page": page, "limit": limit, "total": total, "pages": max(1, math.ceil(total / limit))}}

    def check_limit(limit: int):
        if limit > st().config.max_page_size or limit < 1:
            return JSONResponse({"success": False, "error": f"limit must be 1..{st().config.max_page_size}"}, status_code=422)
        return None

    @app.get("/api/public/inventory/warehouses")
    def warehouses():
        return {"success": True, "data": st().data.warehouses}

    @app.get("/api/public/inventory/products")
    def products(page: int = 1, limit: int = 50):
        if (bad := check_limit(limit)):
            return bad
        return inv_page([p for p in st().data.products if p["status"] == "active"], page, limit)

    @app.get("/api/public/inventory/products/{pid}")
    def product(pid: int):
        p = next((p for p in st().data.products if p["id"] == pid), None)
        return {"success": True, "data": p} if p else JSONResponse({"success": False}, status_code=404)

    @app.get("/api/public/inventory/variants")
    def variants(page: int = 1, limit: int = 50):
        if (bad := check_limit(limit)):
            return bad
        totals: dict[int, int] = {}
        for lot in st().data.lots:
            totals[lot["variant_id"]] = totals.get(lot["variant_id"], 0) + lot["quantity"]
        rows = [{**v, "stock_total": totals.get(v["id"], 0)} for v in st().data.variants]
        return inv_page(rows, page, limit)

    @app.get("/api/public/inventory/variants/{vid}")
    def variant(vid: int):
        v = next((v for v in st().data.variants if v["id"] == vid), None)
        return {"success": True, "data": v} if v else JSONResponse({"success": False}, status_code=404)

    @app.get("/api/public/inventory/variants/{vid}/stock")
    def variant_stock(vid: int):
        return {"success": True, "data": [lot for lot in st().data.lots if lot["variant_id"] == vid]}

    @app.get("/api/public/inventory/variants/{vid}/lots")
    def variant_lots(vid: int):
        return {"success": True, "data": [lot for lot in st().data.lots if lot["variant_id"] == vid]}

    def movement_rows(variant_id: int | None, warehouse_id: int | None, reason: str | None, reference_type: str | None,
                      reference_id: int | None, date_from: str | None, date_to: str | None) -> list[dict[str, Any]]:
        rows = st().movements
        out = []
        for m in reversed(rows):  # newest first
            if variant_id is not None and m["variant_id"] != variant_id:
                continue
            if warehouse_id is not None and m["warehouse_id"] != warehouse_id:
                continue
            if reason and m["reason"] != reason:
                continue
            if reference_type and m["reference_type"] != reference_type:
                continue
            if reference_id is not None and m["reference_id"] != reference_id:
                continue
            day = m["created_at"][:10]
            if date_from and day < date_from[:10]:
                continue
            if date_to and day > date_to[:10]:
                continue
            out.append(m)
        return out

    def serve_movements(page: int, limit: int, **filters: Any):
        s = st()
        if (bad := check_limit(limit)):
            return bad
        s.movements_requests += 1
        trigger = s.config.insert_after_movement_requests
        if trigger is not None and s.movements_requests == trigger + 1:
            s.insert_new_movements()
        if page in s.config.missing_pages and page not in s.failed_pages_served:
            s.failed_pages_served.add(page)
            return JSONResponse({"success": False, "error": "temporary failure"}, status_code=500)
        return inv_page(movement_rows(**filters), page, limit)

    @app.get("/api/public/inventory/movements")
    def movements(page: int = 1, limit: int = 50, variant_id: int | None = None, warehouse_id: int | None = None,
                  reason: str | None = None, reference_type: str | None = None, reference_id: int | None = None,
                  date_from: str | None = None, date_to: str | None = None):
        return serve_movements(page, limit, variant_id=variant_id, warehouse_id=warehouse_id, reason=reason,
                               reference_type=reference_type, reference_id=reference_id, date_from=date_from, date_to=date_to)

    @app.get("/api/public/inventory/variants/{vid}/movements")
    def variant_movements(vid: int, page: int = 1, limit: int = 50, date_from: str | None = None, date_to: str | None = None):
        return serve_movements(page, limit, variant_id=vid, warehouse_id=None, reason=None, reference_type=None,
                               reference_id=None, date_from=date_from, date_to=date_to)

    @app.get("/api/public/purchases")
    def purchases(page: int = 1, limit: int = 50):
        rows = [m for m in st().movements if m["reason"] == "purchase_receipt"]
        start = (page - 1) * limit
        return {"success": True, "data": rows[start:start + limit], "page": page, "limit": limit,
                "totalPages": max(1, math.ceil(len(rows) / limit))}

    @app.get("/api/public/tickets")
    def tickets(page: int = 1, limit: int = 50):
        rows = [m for m in st().movements if m["reason"] == "sale_shipment"]
        start = (page - 1) * limit
        return {"success": True, "data": rows[start:start + limit], "total": len(rows)}

    # --- admin surface for tests and Compose (never part of the real API)
    @app.get("/__mock__/requests")
    def requests_log():
        return st().request_log

    @app.post("/__mock__/reset")
    def reset():
        st().reset()
        return {"ok": True}

    @app.post("/__mock__/config")
    async def configure(request: Request):
        body = await request.json()
        for k, v in body.items():
            if not hasattr(st().config, k):
                return JSONResponse({"error": f"unknown option {k}"}, status_code=422)
            setattr(st().config, k, set(v) if k == "missing_pages" else v)
        return {"ok": True}

    @app.post("/__mock__/load")
    async def load_dataset(request: Request):
        """Replace the whole dataset (local export loader, MMI 004). The mock is test support and refuses this in prod/staging."""
        if os.environ.get("MMI_ENV") in {"prod", "staging"}:
            return JSONResponse({"error": "not available in this environment"}, status_code=403)
        body = await request.json()
        s = st()
        s.data = Dataset(s.data.config, body["warehouses"], body["products"], body["variants"],
                         {int(k): v for k, v in body["suppliers"].items()}, body["lots"], body["movements"])
        s.reset()
        return {"ok": True, "variants": len(s.data.variants), "movements": len(s.movements)}

    @app.get("/__mock__/health")
    def health():
        return {"ok": True, "movements": len(st().movements)}

    return app
