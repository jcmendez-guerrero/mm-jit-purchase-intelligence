"""Forecast read API for procurement-service (service identity): the latest completed run's values."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from typing import Any

from audit import append
from db.tables import forecast_runs, forecast_values
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from mmi_common.errors import error_code
from parameters import ParameterConflict, ParameterError, listing, save_parameter
from pydantic import BaseModel
from runs.accuracy import latest_accuracy
from runs.runner import run_forecast
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Connection, Engine

_engine: Engine | None = None


class ParameterBody(BaseModel):
    value: str
    valid_from: date | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(os.environ["MMI_DATABASE_URL"], pool_pre_ping=True)
    return _engine


UPPER_LEVEL = "0.95"          # the service level shown as the upper end of the uncertainty


def build_router(app: FastAPI) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def conn_dep(engine: Engine = Depends(get_engine)) -> Iterator[Connection]:
        with engine.begin() as conn:
            yield conn

    @router.get("/forecasts/latest")
    def latest(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        run = conn.execute(select(forecast_runs).where(forecast_runs.c.status == "completed").order_by(forecast_runs.c.finished_at.desc()).limit(1)).first()
        if run is None:
            raise HTTPException(404, "no_forecast_run")
        variants: dict[int, dict[str, Any]] = {}
        for r in conn.execute(select(forecast_values).where(forecast_values.c.run_id == run.id).order_by(forecast_values.c.variant_id, forecast_values.c.horizon_days)).all():
            v = variants.setdefault(r.variant_id, {"eligible": r.eligible, "policy": r.policy_used, "reasons": [x for x in r.reasons.split(",") if x],
                                                   "service_level": str(r.service_level), "horizons": {}})
            v["horizons"][str(r.horizon_days)] = {"mean": r.mean, "quantiles": r.quantiles}
        return {"run_id": run.id, "input_hash": run.input_hash, "dataset_version_id": run.dataset_version_id, "through_day": run.through_day, "total": run.total_count, "eligible": run.eligible_count,
                "variants": {str(k): v for k, v in variants.items()}}

    @router.get("/forecasts/variant/{variant_id}")
    def variant_forecast(variant_id: int = Path(ge=1), conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """Whether this product's figure in the latest run rests on imported estimates (FR-008). Read-only; no quantities."""
        run = conn.execute(select(forecast_runs).where(forecast_runs.c.status == "completed").order_by(forecast_runs.c.finished_at.desc()).limit(1)).first()
        if run is None:
            raise HTTPException(404, "no_forecast_run")
        rows = conn.execute(select(forecast_values).where(forecast_values.c.run_id == run.id, forecast_values.c.variant_id == variant_id)
                            .order_by(forecast_values.c.horizon_days)).all()
        if not rows:
            raise HTTPException(404, "no_forecast_for_variant")
        row = rows[0]
        horizons = []
        for r in rows:
            if not r.eligible or r.mean is None:
                continue                                                          # a min/max line has no mean to show
            q = (r.quantiles or {}).get(UPPER_LEVEL)
            horizons.append({"days": r.horizon_days, "mean": float(r.mean), "upper": max(float(q), float(r.mean)) if q is not None else float(r.mean)})
        return {"run_id": run.id, "variant_id": variant_id, "eligible": bool(row.eligible), "policy": row.policy_used, "seed_used": "seed_used" in (row.reasons or "").split(","),
                "horizons": horizons, "upper_level": UPPER_LEVEL}

    @router.get("/accuracy")
    def accuracy(history: int = Query(default=0, ge=0, le=52), conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return latest_accuracy(conn, history)

    @router.get("/runs")
    def runs(limit: int = 20, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        rows = conn.execute(select(forecast_runs).order_by(forecast_runs.c.started_at.desc()).limit(max(1, min(limit, 100)))).all()
        return {"runs": [{"id": r.id, "started_at": r.started_at.isoformat(), "status": r.status, "through_day": r.through_day, "total": r.total_count, "eligible": r.eligible_count,
                          "dataset_version_id": r.dataset_version_id, "parameter_version_ids": r.parameter_version_ids,
                          "rule_version_ids": r.rule_version_ids} for r in rows]}

    @router.get("/parameters")
    def read_parameters(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        d = datetime.now(UTC).date()
        return {"as_of": d.isoformat(), "parameters": listing(conn, d)}

    @router.put("/parameters/{key}")
    def put_parameter(key: str, body: ParameterBody, if_match: str | None = Header(default=None), conn: Connection = Depends(conn_dep),
                      principal: Any = Depends(require("buyer"))) -> Any:
        current = next((p["revision"] for p in listing(conn, datetime.now(UTC).date()) if p["key"] == key), None)
        if current is None:
            raise HTTPException(422, "unknown_parameter")
        expected: int | None = None
        if if_match is not None:
            raw = if_match.strip().removeprefix("W/").strip('"')
            if not raw.isdigit():
                raise HTTPException(400, "request_invalid")
            expected = int(raw)
        if expected is None and current > 0:
            raise HTTPException(428, "revision_required")
        try:
            rev = save_parameter(conn, key, body.value, principal.subject, valid_from=body.valid_from, expected_revision=expected if expected is not None else 0)
        except ParameterConflict as exc:
            return JSONResponse({"detail": exc.code, "current_version": exc.current_revision}, status_code=412)
        except ParameterError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        return {"key": key, "revision": rev}

    @router.post("/runs", status_code=202)
    def request_run(engine: Engine = Depends(get_engine), principal: Any = Depends(require())) -> dict[str, Any]:
        """Re-forecast on request (buyers and admins). Unchanged inputs and parameters reuse the existing run (nothing is duplicated)."""
        if not ({"buyer", "admin"} & set(principal.roles)):
            raise HTTPException(403, "auth_forbidden_role")
        source, writer = getattr(app.state, "series_source", None), getattr(app.state, "blob_writer", None)
        if source is None or writer is None:
            raise HTTPException(503, "not_configured")
        res = run_forecast(engine, source, writer)
        if "admin" in principal.roles:
            with engine.begin() as conn:
                append(conn, principal.subject, "forecast.rerun", "forecast_run", res.run_id, after={"reused": res.reused})
        return {"run_id": res.run_id, "reused": res.reused, "eligible": res.eligible}

    return router
