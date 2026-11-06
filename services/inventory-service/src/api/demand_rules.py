"""T086 / T088 / T087: demand exclusions, censoring rules, category history and the criticality view for the policy console."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from classification.run import compute_segments, history_for
from db.tables import products, variants
from demand.rebuild import rebuild
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from mmi_common.errors import error_code
from projections.rules import (
    RuleError,
    add_exclusion,
    list_exclusions,
    list_rules,
    set_censoring_rule,
    set_exclusion_active,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.engine import Connection


class ExclusionBody(BaseModel):
    variant_id: int | None = Field(default=None, ge=1)
    from_day: date
    to_day: date
    reason: str = Field(min_length=1, max_length=500)


class ActiveBody(BaseModel):
    active: bool


class RuleBody(BaseModel):
    value: int


def build_rules_router(app: FastAPI, conn_dep: Callable[..., Connection]) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def refresh(conn: Connection) -> None:
        """A rule change takes effect on the next forecast input: rebuild the series and re-evaluate categories now (history keeps the reason)."""
        rebuild(conn)
        compute_segments(conn)

    @router.get("/demand-rules")
    def read_rules(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return {"exclusions": list_exclusions(conn), "rules": list_rules(conn)}

    @router.post("/demand-rules/exclusions", status_code=201)
    def create_exclusion(body: ExclusionBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            xid = add_exclusion(conn, body.variant_id, body.from_day, body.to_day, body.reason, principal.subject)
        except RuleError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        refresh(conn)
        return {"id": xid}

    @router.put("/demand-rules/exclusions/{xid}")
    def toggle_exclusion(xid: int, body: ActiveBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            set_exclusion_active(conn, xid, body.active, principal.subject)
        except RuleError as exc:
            raise HTTPException(404, error_code(exc)) from exc
        refresh(conn)
        return {"id": xid, "active": body.active}

    @router.put("/demand-rules/rules/{rule}")
    def put_rule(rule: str, body: RuleBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            rev = set_censoring_rule(conn, rule, body.value, principal.subject)
        except RuleError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        refresh(conn)
        return {"rule": rule, "value": body.value, "revision": rev}

    @router.get("/segments/{variant_id}/history")
    def segment_history(variant_id: int, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return {"variant_id": variant_id, "history": history_for(conn, variant_id)}

    @router.get("/criticality")
    def criticality_view(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """Products with their manual clinical-criticality flag (edited with PUT /products/{id}/criticality). Never inferred."""
        rows = conn.execute(select(products.c.external_id, products.c.name, products.c.clinical_critical).order_by(products.c.name)).all()
        counts = {r.product_id: r.n for r in conn.execute(select(variants.c.product_id, func.count().label("n")).group_by(variants.c.product_id)).all()}
        return {"products": [{"product_id": r.external_id, "name": r.name, "clinical_critical": bool(r.clinical_critical), "variants": counts.get(r.external_id, 0)} for r in rows]}

    return router
