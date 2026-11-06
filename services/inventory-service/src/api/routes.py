"""T057: inventory API (variant detail, review list and decisions). Called by api-bff with a service identity."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

from classification.criticality import CriticalityError, set_critical
from classification.run import load_series
from classification.service_levels import effective_target, history
from db.tables import (
    ALL_WAREHOUSES,
    demand_observations,
    flow_series,
    product_segments,
    products,
    stock_history,
    stock_lots,
    stock_movements,
    stock_snapshots,
    variants,
)
from demand.rebuild import rebuild
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from mmi_common.errors import error_code
from pydantic import BaseModel, Field
from quality.review import ReviewError, decide, list_open
from risk.daily import evaluate_risks
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection, Engine

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(os.environ["MMI_DATABASE_URL"], pool_pre_ping=True)
    return _engine


class CriticalityBody(BaseModel):
    critical: bool


class DecisionBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    decision: str


def build_router(app: FastAPI, history_days: int = 90) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def conn_dep(engine: Engine = Depends(get_engine)) -> Iterator[Connection]:
        with engine.begin() as conn:
            yield conn

    @router.get("/risk")
    def list_risks(warehouse_id: int | None = None, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> list[dict[str, Any]]:
        return evaluate_risks(conn, warehouse_id=warehouse_id)

    @router.get("/variants/{variant_id}")
    def variant_detail(variant_id: int, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        v = conn.execute(select(variants).where(variants.c.external_id == variant_id)).first()
        if v is None:
            raise HTTPException(404, "unknown_variant")
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
            raise HTTPException(409, error_code(exc)) from exc
        rebuild(conn)  # released movements enter the series immediately; ignored ones stay out
        return {"decided": n}

    @router.put("/products/{product_id}/criticality")
    def criticality(product_id: int, body: CriticalityBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            changed = set_critical(conn, product_id, body.critical, principal.subject)
        except CriticalityError as exc:
            raise HTTPException(404, error_code(exc)) from exc
        return {"product_id": product_id, "clinical_critical": body.critical, "changed": changed}

    @router.get("/service-levels")
    def service_levels(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return {"history": history(conn)}

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

    @router.get("/export/stock")
    def export_stock(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """Per-variant stock, lots, classification and service-level target: the proposal inputs procurement-service cannot read directly."""
        now = datetime.now(UTC)
        latest = conn.execute(select(func.max(stock_snapshots.c.snapshot_date)).where(stock_snapshots.c.warehouse_id == ALL_WAREHOUSES)).scalar()
        snaps = {r.variant_id: r for r in conn.execute(select(stock_snapshots).where(stock_snapshots.c.warehouse_id == ALL_WAREHOUSES,
                                                                                    stock_snapshots.c.snapshot_date == latest)).all()} if latest else {}
        segs = {r.variant_id: r for r in conn.execute(select(product_segments)).all()}
        crit = {r.external_id for r in conn.execute(select(products.c.external_id).where(products.c.clinical_critical)).all()}
        lots: dict[int, list[dict[str, Any]]] = {}
        for r in conn.execute(select(stock_lots).order_by(stock_lots.c.variant_id, stock_lots.c.expiry_date)).all():
            lots.setdefault(r.variant_id, []).append({"warehouse_id": r.warehouse_id, "batch_number": r.batch_number, "quantity": r.quantity,
                                                      "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None})
        out = []
        for v in conn.execute(select(variants).order_by(variants.c.external_id)).all():
            seg, snap = segs.get(v.external_id), snaps.get(v.external_id)
            pid = v.product_id or 0
            out.append({
                "variant_id": v.external_id, "product_id": v.product_id, "sku": v.sku, "name": v.name, "pack_size": v.pack_size,
                "on_hand": snap.on_hand if snap else 0, "available": snap.available if snap else 0, "lots": lots.get(v.external_id, []),
                "segment": None if seg is None else {"abc": seg.abc, "pattern": seg.pattern, "forecast_eligible": seg.forecast_eligible},
                "clinical_critical": v.product_id in crit,
                "service_level": str(effective_target(conn, pid, seg.abc if seg else "C", seg.pattern if seg else "intermittent", v.product_id in crit, now))})
        return {"snapshot_date": latest.isoformat() if latest else None, "count": len(out), "variants": out}

    @router.get("/receipts")
    def receipts(after_id: int = 0, limit: int = 1000, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """Supplier receipts (purchase_receipt movements) after a movement id, oldest first, for order reconciliation."""
        rows = conn.execute(select(stock_movements).where(stock_movements.c.reason == "purchase_receipt", stock_movements.c.quantity > 0,
                                                          stock_movements.c.external_id > after_id, stock_movements.c.quarantined.is_(False))
                            .order_by(stock_movements.c.external_id).limit(min(limit, 5000))).all()
        return {"receipts": [{"movement_id": r.external_id, "variant_id": r.variant_id, "qty": r.quantity,
                              "reference": r.reference_number if r.reference_number is not None else r.reference_id,
                              "batch_number": r.batch_number} for r in rows]}

    from api.dashboard import build_dashboard_router
    from api.demand_rules import build_rules_router
    from api.lots import build_lots_router

    router.include_router(build_dashboard_router(app, conn_dep))
    router.include_router(build_lots_router(app, conn_dep))
    router.include_router(build_rules_router(app, conn_dep))
    return router
