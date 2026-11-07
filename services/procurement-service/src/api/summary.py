"""T130: proposed-spend summary for the dashboard: the newest live proposal's total and its split by supplier, against the budget in force."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from db.tables import proposals, supplier_order_groups, suppliers
from fastapi import APIRouter, Depends, FastAPI
from policies.service import effective_weekly_budget
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from api.costs import get_engine

Q2 = Decimal("0.01")


def spend_summary(conn: Connection, supplier_id: str | None = None) -> dict[str, Any]:
    p = conn.execute(select(proposals).where(proposals.c.status != "superseded").order_by(proposals.c.created_at.desc()).limit(1)).first()
    cap = effective_weekly_budget(conn, datetime.now(UTC).date())
    base: dict[str, Any] = {"proposal_id": None, "week": None, "status": None, "total": "0.00", "by_supplier": [], "budget": None if cap is None else str(cap.quantize(Q2)), "over_budget": False}
    if p is None:
        return base
    names = {r.id: r.name for r in conn.execute(select(suppliers.c.id, suppliers.c.name)).all()}
    groups = conn.execute(select(supplier_order_groups).where(supplier_order_groups.c.proposal_id == p.id).order_by(supplier_order_groups.c.supplier_id)).all()
    if supplier_id is not None:
        groups = [g for g in groups if g.supplier_id == supplier_id]
    by = [{"supplier_id": g.supplier_id, "supplier_name": names.get(g.supplier_id), "total": str(Decimal(str(g.total_cost)).quantize(Q2))} for g in groups]
    total = sum((Decimal(str(g.total_cost)) for g in groups), Decimal(0))
    limit = Decimal(str(p.budget)) if p.budget is not None else cap
    return {**base, "proposal_id": p.id, "week": p.week, "status": p.status, "total": str(total.quantize(Q2)), "by_supplier": by,
            "budget": None if limit is None else str(limit.quantize(Q2)), "over_budget": bool(limit is not None and supplier_id is None and total > limit)}


def build_router(app: FastAPI) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def conn_dep(engine: Engine = Depends(get_engine)) -> Iterator[Connection]:
        with engine.begin() as conn:
            yield conn

    @router.get("/summary/spend")
    def spend(supplier_id: str | None = None, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return spend_summary(conn, supplier_id)

    return router
