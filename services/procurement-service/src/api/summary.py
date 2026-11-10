"""T130: proposed-spend summary for the dashboard: the newest live proposal's total and its split by supplier, against the budget in force."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from db.tables import inbound_order_lines, inbound_orders, proposals, supplier_order_groups, suppliers
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from policies.service import effective_weekly_budget
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from api.costs import get_engine

Q2 = Decimal("0.01")
MAX_RANGE_DAYS = 366
MONEY_ROLES = frozenset({"buyer", "approver", "admin"})        # same rule as inventory dashboard/roles.py and the gateway (FR-017)


def open_orders_amount(conn: Connection, supplier_id: str | None = None) -> Decimal:
    """Confirmed orders not yet received: what is still to arrive, at the confirmed cost (feature 006, capital tied up)."""
    q = (select(inbound_order_lines.c.qty, inbound_order_lines.c.received_qty, inbound_order_lines.c.confirmed_cost_with_recargo)
         .join(inbound_orders, inbound_orders.c.id == inbound_order_lines.c.order_id).where(inbound_orders.c.status.in_(("confirmed", "partially_received"))))
    if supplier_id is not None:
        q = q.where(inbound_orders.c.supplier_id == supplier_id)
    return sum((max(r.qty - r.received_qty, 0) * Decimal(str(r.confirmed_cost_with_recargo)) for r in conn.execute(q)), Decimal(0))


def confirmed_spend_by_week(conn: Connection, monday_from: date, monday_to: date, supplier_id: str | None) -> dict[date, Decimal]:
    """Spend = supplier orders already confirmed (not cancelled), at their confirmed cost, in the ISO week of their confirmation (FR-026)."""
    start, end = datetime.combine(monday_from, datetime.min.time(), UTC), datetime.combine(monday_to + timedelta(days=7), datetime.min.time(), UTC)
    q = (select(inbound_orders.c.confirmed_at, inbound_order_lines.c.qty, inbound_order_lines.c.confirmed_cost_with_recargo)
         .join(inbound_orders, inbound_orders.c.id == inbound_order_lines.c.order_id)
         .where(inbound_orders.c.status != "cancelled", inbound_orders.c.confirmed_at >= start, inbound_orders.c.confirmed_at < end))
    if supplier_id is not None:
        q = q.where(inbound_orders.c.supplier_id == supplier_id)
    out: dict[date, Decimal] = {}
    for r in conn.execute(q):
        day = r.confirmed_at.date()
        week = day - timedelta(days=day.weekday())
        out[week] = out.get(week, Decimal(0)) + r.qty * Decimal(str(r.confirmed_cost_with_recargo))
    return out


def range_summary(conn: Connection, date_from: date, date_to: date, supplier_id: str | None = None) -> dict[str, Any]:
    """Research R15: per ISO week whose Monday falls in the range, the cap in force that Monday, the spend (confirmed orders) and the proposed spend (the newest live
    proposal's supplier groups whose order is not confirmed yet, drafts included). The two are never added or named after each other."""
    mondays, monday = [], date_from + timedelta(days=(7 - date_from.weekday()) % 7)
    while monday <= date_to:
        mondays.append(monday)
        monday += timedelta(days=7)
    confirmed = confirmed_spend_by_week(conn, mondays[0], mondays[-1], supplier_id) if mondays else {}
    weeks = []
    for monday in mondays:
        iso = monday.isocalendar()
        p = conn.execute(select(proposals.c.id).where(proposals.c.week == f"{iso.year}-W{iso.week:02d}", proposals.c.status != "superseded").order_by(proposals.c.created_at.desc()).limit(1)).first()
        q = select(supplier_order_groups.c.total_cost).where(supplier_order_groups.c.proposal_id == (p.id if p else None))
        q = q.where(~select(inbound_orders.c.id).where(inbound_orders.c.proposal_id == supplier_order_groups.c.proposal_id, inbound_orders.c.supplier_id == supplier_order_groups.c.supplier_id,
                                                      inbound_orders.c.status != "cancelled").exists())
        if supplier_id is not None:
            q = q.where(supplier_order_groups.c.supplier_id == supplier_id)
        proposed = sum((Decimal(str(r.total_cost)) for r in conn.execute(q)), Decimal(0))
        cap = effective_weekly_budget(conn, monday)
        weeks.append({"week_start": monday.isoformat(), "cap": None if cap is None else str(cap.quantize(Q2)), "proposed": str(proposed.quantize(Q2)),
                      "spend": str(confirmed.get(monday, Decimal(0)).quantize(Q2))})
    caps = [Decimal(w["cap"]) for w in weeks if w["cap"] is not None]
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "weeks": weeks, "budget": str(sum(caps, Decimal(0)).quantize(Q2)) if caps else None,
            "proposed": str(sum((Decimal(w["proposed"]) for w in weeks), Decimal(0)).quantize(Q2)), "spend": str(sum((Decimal(w["spend"]) for w in weeks), Decimal(0)).quantize(Q2))}


def spend_summary(conn: Connection, supplier_id: str | None = None, date_from: date | None = None, date_to: date | None = None) -> dict[str, Any]:
    p = conn.execute(select(proposals).where(proposals.c.status != "superseded").order_by(proposals.c.created_at.desc()).limit(1)).first()
    cap = effective_weekly_budget(conn, datetime.now(UTC).date())
    base: dict[str, Any] = {"proposal_id": None, "week": None, "status": None, "total": "0.00", "by_supplier": [], "budget": None if cap is None else str(cap.quantize(Q2)), "over_budget": False,
            "open_orders": str(open_orders_amount(conn, supplier_id).quantize(Q2)), "range": None if date_from is None or date_to is None else range_summary(conn, date_from, date_to, supplier_id)}
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
    def spend(supplier_id: str | None = None, date_from: date | None = None, date_to: date | None = None, conn: Connection = Depends(conn_dep),
              _p: Any = Depends(require())) -> dict[str, Any]:
        if not MONEY_ROLES & set(_p.roles):                    # the figures are money: the gateway hides them, and the service refuses too
            raise HTTPException(403, "forbidden")
        if (date_from is None) != (date_to is None) or (date_from and date_to and not 0 <= (date_to - date_from).days < MAX_RANGE_DAYS):
            raise HTTPException(422, "invalid_range")
        return spend_summary(conn, supplier_id, date_from, date_to)

    return router
