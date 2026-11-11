"""T084 / T089: purchase policies, budget caps, stocking settings and safety-stock override requests (contracts/bff-api.delta)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from db.tables import audit_events, policy_sets
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from mmi_common.errors import error_code
from policies.overrides import (
    OverrideRequestError,
    decide,
    drift,
    effective_for_variant,
    queue,
    recommended_safety_stock,
    request_override,
    revert,
)
from policies.preview import preview_policy
from policies.service import (
    FIELDS,
    SEGMENTS,
    PolicyConflict,
    PolicyError,
    PolicyValues,
    budget_cap_revision,
    clear_policy,
    effective_view,
    effective_weekly_budget,
    history,
    listing,
    policy_row,
    save_budget_cap,
    save_policy,
    sku_for_variant,
    validate_key,
    variant_for_sku,
    variant_known,
)
from policies.stocking import get_stocking, save_stocking
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.engine import Connection

from api.costs import get_engine
from api.terms import parse_if_match

# What the admin audit view may show of a stored event: rule values and bookkeeping only, never a typed reason or an ERP id.
AUDIT_VIEW_KEYS = ("scope", "key", "revision", "valid_from", *FIELDS, "period", "scope_key", "amount", "mode", "floor", "field", "recommended", "requested", "status",
                   "recommendation_changed", "current_recommended")


class PolicyBody(BaseModel):
    service_level_pct: Decimal | None = Field(default=None, ge=0, le=100)
    safety_stock_units: int | None = Field(default=None, ge=0, le=1_000_000)
    min_units: int | None = Field(default=None, ge=0, le=1_000_000)
    max_units: int | None = Field(default=None, ge=0, le=1_000_000)
    replenishment_cadence_days: int | None = Field(default=None, ge=0, le=1000)
    valid_from: date | None = None

    def values(self) -> PolicyValues:
        return PolicyValues(None if self.service_level_pct is None else self.service_level_pct / 100, self.safety_stock_units, self.min_units, self.max_units,
                            self.replenishment_cadence_days)


class BudgetBody(BaseModel):
    period: str
    scope: str = "global"
    scope_key: str | None = None
    amount: Decimal = Field(ge=0)
    valid_from: date | None = None


class StockingBody(BaseModel):
    stocking_mode: str
    min_floor_units: int = Field(ge=0, le=100_000)


class OverrideBody(BaseModel):
    sku: str = Field(min_length=1, max_length=60)
    field: str
    requested_value: int = Field(ge=0, le=1_000_000)
    reason: str = Field(min_length=1, max_length=500)


def _json_override(r: Any) -> dict[str, Any]:
    return {"id": r.id, "variant_id": r.variant_id, "field": r.field, "recommended_value": r.recommended_value, "requested_value": r.requested_value, "reason": r.reason,
            "status": r.status, "requested_by": r.requested_by, "requested_at": r.requested_at.isoformat(), "decided_by": r.decided_by,
            "decided_at": r.decided_at.isoformat() if r.decided_at else None, "recommendation_changed": r.recommendation_changed}


def override_json(conn: Connection, r: Any) -> dict[str, Any]:
    """The request as the API shows it: for a pending safety-stock request, whether the recommendation has moved since and what it is now."""
    changed, current = drift(conn, r, lambda c, v: recommended_safety_stock(c, v))
    return {**_json_override(r), "sku": sku_for_variant(conn, int(r.variant_id)), "recommendation_changed": changed, "current_recommended": current}


def build_router(app: FastAPI) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def conn_dep(engine: Any = Depends(get_engine)):  # type: ignore[no-untyped-def]
        with engine.begin() as conn:
            yield conn

    def today() -> date:
        return datetime.now(UTC).date()

    def pol_json(r: Any) -> dict[str, Any]:
        return {"valid_from": r.valid_from.isoformat(), "revision": r.revision, "changed_by": r.changed_by,
                **{f: (None if getattr(r, f) is None else str(getattr(r, f))) for f in FIELDS}}

    def internal_key(conn: Connection, scope: str, key: str) -> str:
        """People type the SKU for product scope; the variant id stays inside the platform. Unknown or ambiguous SKUs are refused."""
        if scope != "product":
            return key
        try:
            return str(variant_for_sku(conn, key))
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc

    @router.get("/policies")
    def list_policies(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        d = today()
        w = effective_weekly_budget(conn, d)
        rows = listing(conn, d)
        orphaned = 0
        for r in rows:
            if r["scope"] == "product":
                vid = int(r["key"])
                r["variant_id"] = vid                                  # internal; the gateway removes it before it reaches the browser
                if variant_known(conn, vid):
                    r["key"] = sku_for_variant(conn, vid) or r["key"]
                else:                                                  # kept and flagged, never dropped; the ERP id is not shown as a key
                    r["key"] = None
                    r["orphaned"] = True
                    orphaned += 1
        return {"as_of": d.isoformat(), "policies": rows, "weekly_budget": None if w is None else str(w.quantize(Decimal("0.01"))), "orphaned": orphaned,
                "weekly_budget_revision": budget_cap_revision(conn, "week", "global", None)}

    @router.get("/products/{sku}/effective-policy")
    def effective_policy(sku: str, segments: str = Query(default="", max_length=60), conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        try:
            vid = variant_for_sku(conn, sku)
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        segs = tuple(s for s in segments.split(",") if s)
        if any(s not in SEGMENTS for s in segs):
            raise HTTPException(422, "policy_out_of_range")
        return {"sku": sku.strip(), "as_of": today().isoformat(), "rules": effective_view(conn, vid, segs, today())}

    @router.get("/policy-audit")
    def policy_audit(limit: int = Query(default=100, ge=1, le=500), prefix: str = Query(default="", max_length=80, pattern="^[a-z_.,]*$"),
                     outcome: str | None = Query(default=None, pattern="^(accepted|refused)$"), since: datetime | None = None, until: datetime | None = None,
                     conn: Connection = Depends(conn_dep), _p: Any = Depends(require("admin"))) -> dict[str, Any]:
        """Filters (action prefix, outcome, time range) run in the query, before the row limit, so an old match is never cut by newer rows (FR-013)."""
        own = ("policy.", "budget_cap.", "stocking.", "policy_override.")
        wanted = tuple(p for p in own if not prefix or p in prefix.split(","))
        q = select(audit_events).where(or_(*(audit_events.c.action.like(f"{p}%") for p in wanted)))
        if outcome:
            q = q.where(audit_events.c.action.like("%.refused") if outcome == "refused" else audit_events.c.action.not_like("%.refused"))
        if since:
            q = q.where(audit_events.c.ts >= since)
        if until:
            q = q.where(audit_events.c.ts < until)
        rows = conn.execute(q.order_by(audit_events.c.id.desc()).limit(limit)).all()
        from db.tables import policy_override_requests, product_refs

        def num(v: Any) -> int | None:
            return int(v) if str(v).isdigit() else None

        override_ids = {r.entity_id for r in rows if r.action.startswith("policy_override.")}
        override_variant = ({r.id: int(r.variant_id) for r in conn.execute(select(policy_override_requests.c.id, policy_override_requests.c.variant_id)
                                                                          .where(policy_override_requests.c.id.in_(override_ids))).all()} if override_ids else {})

        def product_key(payload: Any) -> int | None:
            return num(payload.get("key")) if isinstance(payload, dict) and payload.get("scope") == "product" else None

        wanted_variants = {v for r in rows for v in (num(r.entity_id) if r.action.startswith("stocking.") else None, override_variant.get(r.entity_id) if r.action.startswith("policy_override.") else None,
                                                     product_key(r.after)) if v is not None}
        sku_of = ({r.variant_id: str(r.sku).strip() for r in conn.execute(select(product_refs.c.variant_id, product_refs.c.sku).where(product_refs.c.variant_id.in_(wanted_variants))).all()
                   if r.sku is not None} if wanted_variants else {})                                    # one lookup for the page, not one per row

        def shown(payload: Any, product_scope: bool) -> dict[str, Any] | None:
            """Only whitelisted keys, and the SKU where the stored key is a variant id: no ERP id and no typed text reaches the admin view (FR-013, FR-018)."""
            if not isinstance(payload, dict):
                return None
            out = {k: payload[k] for k in AUDIT_VIEW_KEYS if k in payload}
            if product_scope and str(out.get("key", "")).isdigit():
                out["key"] = sku_of.get(int(out["key"])) or None
            return out

        items = []
        for r in rows:
            entity_id = r.entity_id
            if r.action.startswith("stocking."):
                entity_id = sku_of.get(num(r.entity_id), "")
            elif r.action.startswith("policy_override."):
                entity_id = sku_of.get(override_variant.get(r.entity_id), "")
            product = product_key(r.after) is not None
            items.append({"at": r.ts.isoformat(), "actor": r.actor, "action": r.action, "entity": r.entity, "entity_id": entity_id, "before": shown(r.before, product),
                          "after": shown(r.after, product), "outcome": "refused" if r.action.endswith(".refused") else "accepted"})
        return {"items": items}

    @router.get("/policies/{scope}/{key}")
    def get_policy(scope: str, key: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        try:
            validate_key(scope, key if scope != "product" else "1")
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        ikey = internal_key(conn, scope, key)
        cur = policy_row(conn, scope, ikey, today())
        rev = int(conn.execute(select(func.max(policy_sets.c.revision)).where(policy_sets.c.scope == scope, policy_sets.c.key == ikey)).scalar() or 0)
        return {"scope": scope, "key": key, "revision": rev, "current": None if cur is None else pol_json(cur), "history": history(conn, scope, ikey)}

    def _expected(header: str | None, conn: Connection, scope: str, key: str) -> int | None:
        exp = parse_if_match(header)
        cur = int(conn.execute(select(func.max(policy_sets.c.revision)).where(policy_sets.c.scope == scope, policy_sets.c.key == key)).scalar() or 0)
        if exp is None and cur > 0:
            raise HTTPException(428, "revision_required")
        return exp if exp is not None else 0

    @router.put("/policies/{scope}/{key}")
    def put_policy(scope: str, key: str, body: PolicyBody, if_match: str | None = Header(default=None), conn: Connection = Depends(conn_dep),
                   principal: Any = Depends(require("buyer"))) -> Any:
        try:
            validate_key(scope, key if scope != "product" else "1")
            key = internal_key(conn, scope, key)
            expected = _expected(if_match, conn, scope, key)
            rev = save_policy(conn, scope, key, body.values(), principal.subject, valid_from=body.valid_from, expected_revision=expected)
        except PolicyConflict as exc:
            return JSONResponse({"detail": exc.code, "current_version": exc.current_revision}, status_code=412)
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        return {"revision": rev}

    @router.delete("/policies/{scope}/{key}")
    def clear(scope: str, key: str, if_match: str | None = Header(default=None), conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> Any:
        """Removes an override: a new revision with every field empty, so the lower scope or the default applies again."""
        try:
            validate_key(scope, key if scope != "product" else "1")
            ikey = internal_key(conn, scope, key)
            expected = parse_if_match(if_match)
            if expected is None:
                raise HTTPException(428, "revision_required")
            return {"revision": clear_policy(conn, scope, ikey, principal.subject, expected_revision=expected)}
        except PolicyConflict as exc:
            return JSONResponse({"detail": exc.code, "current_version": exc.current_revision}, status_code=412)
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc

    @router.post("/policies/{scope}/{key}/preview")
    def preview(scope: str, key: str, body: PolicyBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        provider = getattr(app.state, "inputs_provider", None)
        if provider is None:
            raise HTTPException(503, "not_configured")
        try:
            validate_key(scope, key if scope != "product" else "1")
            result = preview_policy(conn, provider, scope, internal_key(conn, scope, key), body.values(), principal.subject, today(), body.valid_from)
            for row in result.get("affected", []):
                row["sku"] = sku_for_variant(conn, int(row["variant_id"]))          # people see the SKU; the gateway drops variant_id
            return result
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        except Exception as exc:
            from proposals.inputs import InputsUnavailableError

            if isinstance(exc, InputsUnavailableError):
                raise HTTPException(503, exc.code if hasattr(exc, "code") else "inventory_unavailable") from exc
            raise

    @router.put("/budget-caps")
    def put_budget(body: BudgetBody, if_match: str | None = Header(default=None), conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> Any:
        exp = parse_if_match(if_match)
        if exp is None and budget_cap_revision(conn, body.period, body.scope, body.scope_key) > 0:
            raise HTTPException(428, "revision_required")
        try:
            cid = save_budget_cap(conn, body.period, body.scope, body.scope_key, body.amount, principal.subject, valid_from=body.valid_from,
                                  expected_revision=exp if exp is not None else 0)
        except PolicyConflict as exc:
            return JSONResponse({"detail": exc.code, "current_version": exc.current_revision}, status_code=412)
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        w = effective_weekly_budget(conn, today())
        return {"id": cid, "revision": budget_cap_revision(conn, body.period, body.scope, body.scope_key),
                "weekly_budget": None if w is None else str(w.quantize(Decimal("0.01")))}

    def variant_of(conn: Connection, sku: str) -> int:
        """People type the SKU; the variant id stays inside the platform. Unknown or ambiguous SKUs are refused."""
        try:
            return variant_for_sku(conn, sku)
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc

    @router.get("/stocking/{sku}")
    def read_stocking(sku: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        variant_id = variant_of(conn, sku)
        return {**get_stocking(conn, variant_id), "sku": sku_for_variant(conn, variant_id)}

    @router.put("/stocking/{sku}")
    def put_stocking(sku: str, body: StockingBody, if_match: str | None = Header(default=None), conn: Connection = Depends(conn_dep),
                     principal: Any = Depends(require("buyer"))) -> Any:
        variant_id = variant_of(conn, sku)
        cur = get_stocking(conn, variant_id)["revision"]
        exp = parse_if_match(if_match)
        if exp is None and cur > 0:
            raise HTTPException(428, "revision_required")
        try:
            rev = save_stocking(conn, variant_id, body.stocking_mode, body.min_floor_units, principal.subject, expected_revision=exp if exp is not None else 0)
        except PolicyConflict as exc:
            return JSONResponse({"detail": exc.code, "current_version": exc.current_revision}, status_code=412)
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        return {"revision": rev}

    @router.get("/policy-overrides")
    def list_overrides(status: str | None = Query(default="pending", pattern="^(pending|approved|rejected|reverted|all)$"), conn: Connection = Depends(conn_dep),
                       _p: Any = Depends(require())) -> list[dict[str, Any]]:
        return [override_json(conn, r) for r in queue(conn, None if status == "all" else status)]

    @router.get("/policy-overrides/recommendation/{sku}")
    def recommendation(sku: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        variant_id = variant_of(conn, sku)
        rec = recommended_safety_stock(conn, variant_id)
        return {"variant_id": variant_id, "sku": sku_for_variant(conn, variant_id), "safety_stock": rec, "effective": effective_for_variant(conn, variant_id, rec)}

    @router.post("/policy-overrides", status_code=201)
    def create_override(body: OverrideBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        variant_id = variant_of(conn, body.sku)
        try:
            r = request_override(conn, variant_id, body.field, body.requested_value, body.reason, principal.subject, recommended_safety_stock(conn, variant_id) if body.field == "safety_stock" else None)
        except OverrideRequestError as exc:
            raise HTTPException(409 if exc.code == "policy_override_pending" else 422, error_code(exc)) from exc
        return {**_json_override(r), "sku": sku_for_variant(conn, variant_id)}

    def _decide(rid: str, approve: bool, conn: Connection, principal: Any) -> dict[str, Any]:
        from db.tables import policy_override_requests

        row = conn.execute(select(policy_override_requests).where(policy_override_requests.c.id == rid)).first()
        current = recommended_safety_stock(conn, row.variant_id) if row is not None and row.field == "safety_stock" else None
        try:
            return _json_override(decide(conn, rid, principal, approve, current))
        except OverrideRequestError as exc:
            status = {"not_an_approver": 403, "policy_override_self_approval": 403, "policy_override_not_found": 404}.get(exc.code, 409)
            raise HTTPException(status, error_code(exc)) from exc

    @router.post("/policy-overrides/{rid}/approve")
    def approve_override(rid: str, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("approver"))) -> dict[str, Any]:
        return _decide(rid, True, conn, principal)

    @router.post("/policy-overrides/{rid}/reject")
    def reject_override(rid: str, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("approver"))) -> dict[str, Any]:
        return _decide(rid, False, conn, principal)

    @router.post("/policy-overrides/{rid}/revert")
    def revert_override(rid: str, conn: Connection = Depends(conn_dep), principal: Any = Depends(require())) -> dict[str, Any]:
        try:
            return _json_override(revert(conn, rid, principal))
        except OverrideRequestError as exc:
            raise HTTPException(404 if exc.code == "policy_override_not_found" else 403 if exc.code == "not_an_approver" else 409, error_code(exc)) from exc

    return router
