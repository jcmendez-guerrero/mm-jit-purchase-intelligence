"""T128: dashboard routes for the buyer console. Read-only; filters come from live data."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from dashboard.drilldown import KINDS, DrillError, drilldown
from dashboard.filters import FilterError, FilterSet
from dashboard.kpis import (
    Filters,
    abc_xyz_distribution,
    compute_summary,
    demand_trend,
    filter_options,
    forecast_series,
)
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlalchemy.engine import Connection


def build_dashboard_router(app: FastAPI, conn_dep: Callable[..., Connection]) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter(prefix="/dashboard")

    def filters(warehouse_id: int | None, category: str | None, family: str | None = None, supplier_id: str | None = None) -> Filters:
        try:
            return FilterSet.parse(datetime.now(UTC).date(), warehouse_id=warehouse_id, category=category, family=family, supplier_id=supplier_id).to_filters()
        except FilterError as exc:
            raise HTTPException(422, "request_invalid") from exc

    def means() -> Any:
        return getattr(app.state, "forecast_means", None)

    @router.get("/filters/options")
    def options(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return filter_options(conn)

    @router.get("/summary")
    def summary(warehouse_id: int | None = None, category: str | None = None, family: str | None = None, supplier_id: str | None = None, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        f = filters(warehouse_id, category, family, supplier_id)
        today = datetime.now(UTC).date()
        try:
            s = compute_summary(conn, today, f, means())
            forecast_ok = True
        except Exception:
            s, forecast_ok = compute_summary(conn, today, f, None), False
        return {**s.as_json(), "forecast_available": forecast_ok and means() is not None}

    @router.get("/demand-trend")
    def trend(days: int = Query(default=60, ge=7, le=365), warehouse_id: int | None = None, category: str | None = None, family: str | None = None, supplier_id: str | None = None,
              conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        today = datetime.now(UTC).date()
        f = filters(warehouse_id, category, family, supplier_id)
        fc = forecast_series(conn, today, f, means())
        return {"from": (today - timedelta(days=days)).isoformat(), "to": date.isoformat(today), "series": demand_trend(conn, today, days, f),
                "estimated": fc["points"], "estimated_basis": {"variants": fc["variants"], "seed_assisted": fc["seed_assisted"], "reason": fc["reason"], "upper_level": "0.95"}}

    @router.get("/drilldown")
    def drill(kind: str = Query(max_length=20), abc: str | None = Query(default=None, max_length=1), xyz: str | None = Query(default=None, max_length=1),
              day: str | None = Query(default=None, max_length=10), warehouse_id: int | None = None, category: str | None = None, family: str | None = None,
              supplier_id: str | None = None, limit: int = Query(default=50, ge=1, le=200), conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        if kind not in KINDS:
            raise HTTPException(422, "request_invalid")
        try:
            return drilldown(conn, kind, datetime.now(UTC).date(), filters(warehouse_id, category, family, supplier_id), means(), abc, xyz, day, limit)
        except DrillError as exc:
            raise HTTPException(422, exc.code) from exc

    @router.get("/abc-xyz")
    def abc_xyz(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return {"cells": [{**d, "value": str(d["value"].quantize(Decimal("0.01")))} for d in abc_xyz_distribution(conn)]}

    return router
