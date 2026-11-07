"""T148/T151 (inventory part): how fresh each projected source is. Read-only, admin only, no row data."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from db.tables import agg_daily_kpis, stock_movements, stock_snapshots
from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import case, func, select
from sqlalchemy.engine import Connection


def _iso(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    return (ts if ts.tzinfo else ts.replace(tzinfo=UTC)).isoformat()      # stored as UTC; some engines drop the zone


def build_status_router(app: FastAPI, conn_dep: Callable[..., Connection]) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter(prefix="/status")

    @router.get("/sources")
    def sources(conn: Connection = Depends(conn_dep), _p: Any = Depends(require("admin"))) -> dict[str, Any]:
        day, snaps = conn.execute(select(func.max(stock_snapshots.c.snapshot_date), func.count()).select_from(stock_snapshots)).one()
        latest, rows, quarantined = conn.execute(select(func.max(stock_movements.c.created_at_utc), func.count(),
                                                        func.coalesce(func.sum(case((stock_movements.c.quarantined.is_(True), 1), else_=0)), 0)).select_from(stock_movements)).one()
        refreshed = conn.execute(select(func.max(agg_daily_kpis.c.refreshed_at))).scalar()
        return {"stock_snapshots": {"latest_day": day.isoformat() if day else None, "rows": int(snaps)},
                "movements": {"rows": int(rows), "quarantined": int(quarantined or 0), "latest_at": _iso(latest)},
                "aggregates": {"refreshed_at": _iso(refreshed)}}

    return router
