"""T024, T025: quality summary, anomaly decisions and recompute (feature 018). Called by api-bff with a service identity.

Products are addressed by SKU; the Siweb variant id stays inside this service. Reads need any signed-in role. Anomaly decisions and
recompute need a buyer or admin; the rule that excluding a day, or reversing an exclusion, needs a fresh second factor lives here; the BFF only reports whether the session has one (header X-Fresh-Second-Factor).
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import httpx
from audit import CLASSES_RECOMPUTED
from audit import append as audit
from classification.policy_source import current_config
from classification.run import compute_segments
from dashboard.filters import FilterError, FilterSet
from db.tables import ALL_WAREHOUSES, stock_history, variants
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel
from quality.portfolio import BUCKETS, ORIGINS, bucket_products, portfolio, rebuild_portfolio
from quality.snapshot import (
    DecisionError,
    NoFlagError,
    build_snapshot,
    decide,
    default_period,
    list_flags,
    needs_second_factor,
    rebuild_snapshots,
    refresh_flags,
)
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

log = logging.getLogger("inventory.quality")


class DecisionBody(BaseModel):
    decision: str
    reason_code: str | None = None


def build_quality_router(app: FastAPI, conn_dep: Callable[..., Connection]) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def buyer_or_admin(principal: Any = Depends(require())) -> Any:
        if not principal.roles & {"buyer", "admin"}:                    # require("a", "b") means both roles; this route accepts either
            raise HTTPException(403, "auth_forbidden_role")
        return principal

    def resolve(conn: Connection, sku: str) -> int:
        ids = list(conn.execute(select(variants.c.external_id).where(variants.c.sku == sku)).scalars())
        if not ids:
            raise HTTPException(404, "quality_product_not_found")
        if len(ids) > 1:
            raise HTTPException(422, "import_ambiguous_sku")           # the same SKU on more than one product is never guessed
        return int(ids[0])

    @router.get("/quality/products/{sku}")
    def summary(sku: str, from_day: date | None = Query(default=None, alias="from"), to_day: date | None = Query(default=None, alias="to"),
                conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        vid = resolve(conn, sku)
        start, end = default_period(conn, vid)
        start, end = from_day or start, to_day or end
        if end < start:
            raise HTTPException(422, "import_date_out_of_range")
        return {"sku": sku, **build_snapshot(conn, vid, start, end)}

    @router.get("/quality/products/{sku}/anomalies")
    def anomalies(sku: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        vid = resolve(conn, sku)
        refresh_flags(conn, vid)
        return {"sku": sku, "anomalies": [{"sku": sku, **f} for f in list_flags(conn, vid)]}

    @router.put("/quality/products/{sku}/anomalies/{day}")
    def put_decision(sku: str, day: date, body: DecisionBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(buyer_or_admin),
                     fresh_second_factor: str | None = Header(default=None, alias="X-Fresh-Second-Factor")) -> dict[str, Any]:
        vid = resolve(conn, sku)
        if needs_second_factor(conn, vid, day, body.decision) and fresh_second_factor != "true":   # the gateway only reports whether the session has a recent check
            raise HTTPException(403, "auth_mfa_stale")
        refresh_flags(conn, vid)
        try:
            changed = decide(conn, vid, day, body.decision, body.reason_code, principal.subject)
        except DecisionError as exc:
            raise HTTPException(422, "quality_decision_invalid") from exc
        except NoFlagError as exc:
            raise HTTPException(404, "quality_anomaly_not_found") from exc
        return {"sku": sku, "day": day.isoformat(), "decision": body.decision, "changed": changed}

    @router.post("/quality/recompute")
    def recompute(conn: Connection = Depends(conn_dep), principal: Any = Depends(buyer_or_admin)) -> dict[str, Any]:
        """Rebuilds flags, snapshots and classes for every product. Runs inside the request for now; the same inputs give the same job id and no duplicate rows."""
        started = time.monotonic()
        ids = [int(v) for v in conn.execute(select(stock_history.c.variant_id).where(stock_history.c.warehouse_id == ALL_WAREHOUSES).distinct()
                                            .order_by(stock_history.c.variant_id)).scalars()]
        service_ids = set(conn.execute(select(variants.c.external_id).where(variants.c.is_service.is_(True))).scalars())
        done = rebuild_snapshots(conn, [vid for vid in ids if vid not in service_ids])        # in blocks, not one set of statements per product
        segments = compute_segments(conn)
        source, run_id, eligibility, state = getattr(app.state, "forecast_eligibility", None), None, None, "not_configured"
        if source is not None:                                              # a forecast service that is down never fails the recompute: products show as pending
            try:
                run_id, eligibility = source.fetch()
                state = "ok" if run_id else "no_run"
            except (httpx.HTTPError, KeyError, ValueError):
                log.warning("FORECAST_ELIGIBILITY_UNAVAILABLE")
                state = "unavailable"
        rebuild_portfolio(conn, eligibility, run_id)
        through = conn.execute(select(func.max(stock_history.c.day))).scalar()
        job = hashlib.sha256(f"{through}|{current_config()[1]}|{done}".encode()).hexdigest()[:16]
        audit(conn, principal.subject, CLASSES_RECOMPUTED, "product_segments", job, after={"products": done, "segments": segments, "config": current_config()[1]})
        log.info("QUALITY_RECOMPUTE_DONE job=%s products=%d eligibility=%s duration_ms=%d", job, done, state, (time.monotonic() - started) * 1000)
        return {"job_id": job, "status": "completed", "products": done, "eligibility": state}

    def parse_filters(category: str | None, supplier_id: str | None, family: str | None) -> Any:
        try:
            return FilterSet.parse(datetime.now(UTC).date(), supplier_id=supplier_id, category=category, family=family).to_filters()
        except FilterError as exc:
            raise HTTPException(422, "request_invalid") from exc

    @router.get("/quality/portfolio")
    def portfolio_view(category: str | None = Query(default=None, max_length=12), supplier_id: str | None = Query(default=None, max_length=36),
                       family: str | None = Query(default=None, max_length=120), origin: str = Query(default="erp", max_length=12),
                       conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """T062: counts by demand class, eligibility and confidence for the whole catalogue or a filtered part; every count drills down to its products."""
        if origin not in ORIGINS:
            raise HTTPException(422, "request_invalid")
        return portfolio(conn, parse_filters(category, supplier_id, family), origin=origin)

    @router.get("/quality/portfolio/products")
    def portfolio_products(bucket: str = Query(max_length=12), key: str = Query(max_length=40), category: str | None = Query(default=None, max_length=12),
                           supplier_id: str | None = Query(default=None, max_length=36), family: str | None = Query(default=None, max_length=120),
                           limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), origin: str = Query(default="erp", max_length=12),
                           conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        if bucket not in BUCKETS or origin not in ORIGINS:
            raise HTTPException(422, "request_invalid")
        return bucket_products(conn, parse_filters(category, supplier_id, family), bucket, key, limit, offset, origin)

    return router
