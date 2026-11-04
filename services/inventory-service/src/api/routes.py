"""T057: inventory API (variant detail, review list and decisions). Called by api-bff with a service identity."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from classification.criticality import CriticalityError, set_critical
from classification.run import load_series
from classification.service_levels import ServiceLevelError, effective_target, history, set_target
from db.tables import (
    ALL_WAREHOUSES,
    demand_observations,
    flow_series,
    product_segments,
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


class CriticalityBody(BaseModel):
    critical: bool


class ServiceLevelBody(BaseModel):
    scope: str
    key: str
    target: Decimal


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
        seg = conn.execute(select(product_segments).where(product_segments.c.variant_id == variant_id)).first()
        return {
            "segment": {"abc": seg.abc, "xyz": seg.xyz, "pattern": seg.pattern, "forecast_eligible": seg.forecast_eligible,
                        "reasons": [r for r in seg.reason.split(",") if r], "metrics": seg.metrics, "computed_at": seg.computed_at.isoformat()} if seg else None,
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

    @router.put("/products/{product_id}/criticality")
    def criticality(product_id: int, body: CriticalityBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            changed = set_critical(conn, product_id, body.critical, principal.subject)
        except CriticalityError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {"product_id": product_id, "clinical_critical": body.critical, "changed": changed}

    @router.get("/service-levels")
    def service_levels(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return {"history": history(conn)}

    @router.put("/service-levels")
    def put_service_level(body: ServiceLevelBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            set_target(conn, body.scope, body.key, body.target, principal.subject)
        except ServiceLevelError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"ok": True}  # applies to proposals created from now on

    @router.get("/export/series")
    def export_series(through_day: date | None = None, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """Per-variant daily demand with segment and service-level target: the forecast job's only input."""
        series = load_series(conn, through_day)
        segs = {r.variant_id: r for r in conn.execute(select(product_segments)).all()}
        prod = {r.external_id: r for r in conn.execute(select(variants.c.external_id, variants.c.product_id)).all()}
        crit = {r.external_id for r in conn.execute(select(products.c.external_id).where(products.c.clinical_critical)).all()}
        now = datetime.now(UTC)
        out = []
        for s in series:
            seg = segs.get(s.variant_id)
            pid = prod[s.variant_id].product_id if s.variant_id in prod else None
            out.append({
                "variant_id": s.variant_id, "product_id": pid, "price": str(s.price), "start_day": s.days[0].isoformat(),
                "demand": s.demand, "censored": s.censored,
                "segment": {"abc": seg.abc, "xyz": seg.xyz, "pattern": seg.pattern, "forecast_eligible": seg.forecast_eligible,
                            "reasons": [r for r in seg.reason.split(",") if r]} if seg else None,
                "service_level": str(effective_target(conn, pid or 0, seg.abc if seg else "C", seg.pattern if seg else "intermittent", pid in crit, now)),
                "clinical_critical": pid in crit})
        return {"through_day": series[0].days[-1].isoformat() if series else None, "count": len(out), "series": out}

    return router
