"""T086 / T088 / T087: demand exclusions, censoring rules, category history, the criticality view and the audit read for the policy console.

Feature 011: products are addressed by SKU (the ERP variant id stays inside), exclusion reasons come from a pick list, every save names the
revision it edited, and the audit never carries free text.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from classification.run import compute_segments, history_for
from db.tables import audit_events, product_segments, products, variants
from demand.publisher import publish_demand_updated
from demand.rebuild import rebuild
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from mmi_common.errors import error_code
from mmi_common.time import get_correlation_id, set_correlation_id
from projections.rules import (
    RuleConflict,
    RuleError,
    add_exclusion,
    censoring_revision,
    exclusion_revision,
    list_exclusions,
    list_rules,
    set_censoring_rule,
    set_exclusion_active,
)
from pydantic import BaseModel, Field
from skus import SkuError, resolve_sku
from sqlalchemy import func, or_, select
from sqlalchemy.engine import Connection


class ExclusionBody(BaseModel):
    sku: str | None = Field(default=None, max_length=60)      # empty means every product
    from_day: date
    to_day: date
    reason_code: str = Field(default="", max_length=40)
    detail: str | None = None


class ActiveBody(BaseModel):
    active: bool


class RuleBody(BaseModel):
    value: int


AUDIT_VIEW_KEYS = ("sku", "from", "to", "reason_code", "active", "value", "revision", "clinical_critical")


def _safe(payload: Any) -> dict[str, Any] | None:
    """Only whitelisted keys reach the audit view: older events carried the typed exclusion reason and the ERP variant id (project rule 7)."""
    return None if not isinstance(payload, dict) else {k: payload[k] for k in AUDIT_VIEW_KEYS if k in payload}


def parse_revision(header: str | None) -> int | None:
    """If-Match carries the revision the editor read, as ``"3"`` or ``3``."""
    if header is None:
        return None
    try:
        return int(header.strip().removeprefix("W/").strip('"'))
    except ValueError as exc:
        raise HTTPException(400, "revision_invalid") from exc


def build_rules_router(app: FastAPI, conn_dep: Callable[..., Connection]) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def refresh(conn: Connection) -> None:
        """A rule change takes effect on the next forecast input: rebuild the series and re-evaluate categories now (history keeps the reason)."""
        result = rebuild(conn)
        compute_segments(conn)
        writer = getattr(app.state, "blob_writer", None)
        if writer is not None and result.through_day is not None:           # tells forecast-service to re-forecast now (unchanged inputs are reused there)
            publish_demand_updated(conn, writer, result.through_day, result.demand_rows, get_correlation_id() or set_correlation_id())

    def conflict(exc: RuleConflict) -> JSONResponse:
        return JSONResponse({"detail": exc.code, "current_version": exc.current_revision}, status_code=412)

    @router.get("/demand-rules")
    def read_rules(conn: Connection = Depends(conn_dep), principal: Any = Depends(require())) -> dict[str, Any]:
        return {"exclusions": list_exclusions(conn, with_detail="admin" in principal.roles), "rules": list_rules(conn)}

    @router.post("/demand-rules/exclusions", status_code=201)
    def create_exclusion(body: ExclusionBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            vid: int | None = None
            sku: str | None = None
            if (body.sku or "").strip():
                vid, _pid, sku = resolve_sku(conn, body.sku or "")
            xid = add_exclusion(conn, vid, body.from_day, body.to_day, body.reason_code, principal.subject, detail=body.detail, sku=sku)
        except SkuError as exc:
            raise HTTPException(422, exc.code) from exc
        except RuleError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        refresh(conn)
        return {"id": xid}

    @router.put("/demand-rules/exclusions/{xid}")
    def toggle_exclusion(xid: int, body: ActiveBody, if_match: str | None = Header(default=None), conn: Connection = Depends(conn_dep),
                         principal: Any = Depends(require("buyer"))) -> Any:
        expected = parse_revision(if_match)
        if expected is None:
            raise HTTPException(428, "revision_required")
        try:
            set_exclusion_active(conn, xid, body.active, principal.subject, expected_revision=expected)
        except RuleConflict as exc:
            return conflict(exc)
        except RuleError as exc:
            raise HTTPException(404, error_code(exc)) from exc
        refresh(conn)
        return {"id": xid, "active": body.active, "revision": exclusion_revision(conn, xid)}

    @router.put("/demand-rules/rules/{rule}")
    def put_rule(rule: str, body: RuleBody, if_match: str | None = Header(default=None), conn: Connection = Depends(conn_dep),
                 principal: Any = Depends(require("buyer"))) -> Any:
        expected = parse_revision(if_match)
        if expected is None and censoring_revision(conn, rule) > 0:
            raise HTTPException(428, "revision_required")
        try:
            rev = set_censoring_rule(conn, rule, body.value, principal.subject, expected_revision=expected if expected is not None else 0)
        except RuleConflict as exc:
            return conflict(exc)
        except RuleError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        refresh(conn)
        return {"rule": rule, "value": body.value, "revision": rev}

    @router.get("/segments/{variant_id}/history")
    def segment_history(variant_id: int, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return {"variant_id": variant_id, "history": history_for(conn, variant_id)}

    @router.get("/criticality")
    def criticality_view(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """Products with their manual clinical-criticality flag (edited with PUT /products/{sku}/criticality). Never inferred."""
        rows = conn.execute(select(products.c.external_id, products.c.name, products.c.clinical_critical).order_by(products.c.name)).all()
        info = {r.product_id: (r.n, r.sku) for r in conn.execute(select(variants.c.product_id, func.count().label("n"), func.min(variants.c.sku).label("sku"))
                                                                  .group_by(variants.c.product_id)).all()}
        return {"products": [{"sku": None if info.get(r.external_id) is None or info[r.external_id][1] is None else str(info[r.external_id][1]).strip(), "name": r.name,
                              "clinical_critical": bool(r.clinical_critical), "variants": info.get(r.external_id, (0, None))[0]} for r in rows]}

    @router.get("/products/{sku}/segments")
    def product_segments_by_sku(sku: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """The segments a policy can be set for, in priority order (critical first, then the ABC class); procurement resolves the effective policy from them."""
        try:
            vid, pid, shown = resolve_sku(conn, sku)
        except SkuError as exc:
            raise HTTPException(422, exc.code) from exc
        crit = bool(pid is not None and conn.execute(select(products.c.clinical_critical).where(products.c.external_id == pid)).scalar())
        abc = conn.execute(select(product_segments.c.abc).where(product_segments.c.variant_id == vid)).scalar()
        return {"sku": shown, "segments": [*(["critical"] if crit else []), *([abc] if abc else [])]}

    @router.get("/policy-audit")
    def policy_audit(limit: int = Query(default=100, ge=1, le=500), conn: Connection = Depends(conn_dep), _p: Any = Depends(require("admin"))) -> dict[str, Any]:
        rows = conn.execute(select(audit_events).where(or_(audit_events.c.action.like("demand_exclusion.%"), audit_events.c.action.like("censoring_rule.%"),
                                                           audit_events.c.action.like("criticality.%"))).order_by(audit_events.c.id.desc()).limit(limit)).all()
        sku_of_product = {r.product_id: str(r.sku).strip() for r in conn.execute(select(variants.c.product_id, func.min(variants.c.sku).label("sku"))
                                                                                   .group_by(variants.c.product_id)).all() if r.sku}
        items = []
        for r in rows:
            entity_id = r.entity_id
            if r.entity == "product":                              # the ERP product id never leaves the service: show a SKU instead
                entity_id = sku_of_product.get(int(r.entity_id), "")
            items.append({"at": r.ts.isoformat(), "actor": r.actor, "action": r.action, "entity": r.entity, "entity_id": entity_id, "before": _safe(r.before), "after": _safe(r.after),
                          "outcome": "accepted"})
        return {"items": items}

    return router
