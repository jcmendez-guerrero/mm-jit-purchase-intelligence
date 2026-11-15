"""T024, T025: quality summary, anomaly decisions and recompute (feature 012). Called by api-bff with a service identity.

Products are addressed by SKU; the Siweb variant id stays inside this service. Reads need any signed-in role. Anomaly decisions and
recompute need a buyer or admin; the fresh second-factor check for excluding a day is enforced by the BFF, which forwards the call.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date
from typing import Any

from audit import CLASSES_RECOMPUTED
from audit import append as audit
from classification.policy_source import current_config
from classification.run import compute_segments
from db.tables import ALL_WAREHOUSES, stock_history, variants
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from quality.snapshot import (
    DecisionError,
    NoFlagError,
    build_snapshot,
    decide,
    default_period,
    list_flags,
    refresh_flags,
)
from sqlalchemy import func, select
from sqlalchemy.engine import Connection


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
    def put_decision(sku: str, day: date, body: DecisionBody, conn: Connection = Depends(conn_dep),
                     principal: Any = Depends(buyer_or_admin)) -> dict[str, Any]:
        vid = resolve(conn, sku)
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
        ids = [int(v) for v in conn.execute(select(stock_history.c.variant_id).where(stock_history.c.warehouse_id == ALL_WAREHOUSES).distinct()
                                            .order_by(stock_history.c.variant_id)).scalars()]
        service_ids = set(conn.execute(select(variants.c.external_id).where(variants.c.is_service.is_(True))).scalars())
        done = 0
        for vid in ids:
            if vid in service_ids:
                continue
            start, end = default_period(conn, vid)
            build_snapshot(conn, vid, start, end)
            done += 1
        segments = compute_segments(conn)
        through = conn.execute(select(func.max(stock_history.c.day))).scalar()
        job = hashlib.sha256(f"{through}|{current_config()[1]}|{done}".encode()).hexdigest()[:16]
        audit(conn, principal.subject, CLASSES_RECOMPUTED, "product_segments", job, after={"products": done, "segments": segments, "config": current_config()[1]})
        return {"job_id": job, "status": "completed", "products": done}

    return router
