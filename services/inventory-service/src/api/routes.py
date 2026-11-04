"""T057: inventory API (variant detail, review list and decisions). Called by api-bff with a service identity."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

from db.tables import (
    ALL_WAREHOUSES,
    demand_observations,
    flow_series,
    products,
    stock_history,
    stock_snapshots,
    variants,
)
from demand.rebuild import rebuild
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from quality.review import ReviewError, decide, list_open
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Connection, Engine

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(os.environ["MMI_DATABASE_URL"], pool_pre_ping=True)
    return _engine


class DecisionBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    decision: str


def build_router(app: FastAPI, history_days: int = 90) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def conn_dep(engine: Engine = Depends(get_engine)) -> Iterator[Connection]:
        with engine.begin() as conn:
            yield conn

    @router.get("/variants/{variant_id}")
    def variant_detail(variant_id: int, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        v = conn.execute(select(variants).where(variants.c.external_id == variant_id)).first()
        if v is None:
            raise HTTPException(404, "variant not found")
        prod = conn.execute(select(products).where(products.c.external_id == v.product_id)).first()
        snap = conn.execute(select(stock_snapshots).where(stock_snapshots.c.variant_id == variant_id, stock_snapshots.c.warehouse_id == ALL_WAREHOUSES)
                            .order_by(stock_snapshots.c.snapshot_date.desc()).limit(1)).first()
        last = conn.execute(select(stock_history.c.day).where(stock_history.c.variant_id == variant_id).order_by(stock_history.c.day.desc()).limit(1)).scalar()
        since = (last or datetime.now(UTC).date()) - timedelta(days=history_days)
        dem = conn.execute(select(demand_observations).where(demand_observations.c.variant_id == variant_id, demand_observations.c.day >= since)
                           .order_by(demand_observations.c.day)).all()
        flows = conn.execute(select(flow_series).where(flow_series.c.variant_id == variant_id, flow_series.c.day >= since)
                             .order_by(flow_series.c.day, flow_series.c.flow)).all()
        hist = conn.execute(select(stock_history).where(stock_history.c.variant_id == variant_id, stock_history.c.day >= since)
                            .order_by(stock_history.c.day)).all()
        return {
            "variant": {"id": v.external_id, "sku": v.sku, "name": v.name, "pack_size": v.pack_size, "uom": v.uom,
                        "product": {"id": v.product_id, "status": prod.status if prod else None}},
            "stock": {"on_hand": snap.on_hand, "available": snap.available, "reserved": snap.reserved, "as_of": snap.snapshot_date.isoformat()} if snap else None,
            "demand": [{"day": r.day.isoformat(), "warehouse_id": r.warehouse_id, "qty": r.demand_qty, "censored": r.censored} for r in dem],
            "flows": [{"day": r.day.isoformat(), "warehouse_id": r.warehouse_id, "flow": r.flow, "qty": r.qty} for r in flows],
            "history": [{"day": r.day.isoformat(), "on_hand": r.on_hand_reconstructed, "censored": r.censored} for r in hist],
            "history_reconciled": all(r.reconciled_ok for r in hist) if hist else None,
        }

    @router.get("/review")
    def review_list(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        items = list_open(conn)
        return {"count": len(items), "items": [
            {"id": i.external_id, "variant_id": i.variant_id, "reason": i.reason, "quantity": i.quantity,
             "created_at": i.created_at_raw, "codes": i.codes} for i in items]}

    @router.post("/review/decisions")
    def review_decide(body: DecisionBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            n = decide(conn, body.ids, body.decision, principal.subject)
        except ReviewError as exc:
            raise HTTPException(409, str(exc)) from exc
        rebuild(conn)  # released movements enter the series immediately; ignored ones stay out
        return {"decided": n}

    return router
