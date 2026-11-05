"""Forecast read API for procurement-service (service identity): the latest completed run's values."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any

from db.tables import forecast_runs, forecast_values
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Connection, Engine

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(os.environ["MMI_DATABASE_URL"], pool_pre_ping=True)
    return _engine


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
        return {"run_id": run.id, "input_hash": run.input_hash, "through_day": run.through_day, "total": run.total_count, "eligible": run.eligible_count,
                "variants": {str(k): v for k, v in variants.items()}}

    return router
