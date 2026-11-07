"""T084 / T089: purchase policies, budget caps, stocking settings and safety-stock override requests (contracts/bff-api.delta)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from db.tables import policy_sets
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
    PolicyConflict,
    PolicyError,
    PolicyValues,
    effective_weekly_budget,
    history,
    listing,
    policy_row,
    save_budget_cap,
    save_policy,
    validate_key,
)
from policies.stocking import get_stocking, save_stocking
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from api.costs import get_engine
from api.terms import parse_if_match


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
    variant_id: int = Field(ge=1)
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
    return {**_json_override(r), "recommendation_changed": changed, "current_recommended": current}


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

    @router.get("/policies")
    def list_policies(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        d = today()
        w = effective_weekly_budget(conn, d)
        return {"as_of": d.isoformat(), "policies": listing(conn, d), "weekly_budget": None if w is None else str(w.quantize(Decimal("0.01")))}

    @router.get("/policies/{scope}/{key}")
    def get_policy(scope: str, key: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        try:
            validate_key(scope, key)
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        cur = policy_row(conn, scope, key, today())
        rev = int(conn.execute(select(func.max(policy_sets.c.revision)).where(policy_sets.c.scope == scope, policy_sets.c.key == key)).scalar() or 0)
        return {"scope": scope, "key": key, "revision": rev, "current": None if cur is None else pol_json(cur), "history": history(conn, scope, key)}

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
            validate_key(scope, key)
            expected = _expected(if_match, conn, scope, key)
            rev = save_policy(conn, scope, key, body.values(), principal.subject, valid_from=body.valid_from, expected_revision=expected)
        except PolicyConflict as exc:
            return JSONResponse({"detail": exc.code, "current_version": exc.current_revision}, status_code=412)
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        return {"revision": rev}

    @router.post("/policies/{scope}/{key}/preview")
    def preview(scope: str, key: str, body: PolicyBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        provider = getattr(app.state, "inputs_provider", None)
        if provider is None:
            raise HTTPException(503, "not_configured")
        try:
            validate_key(scope, key)
            return preview_policy(conn, provider, scope, key, body.values(), principal.subject, today(), body.valid_from)
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        except Exception as exc:
            from proposals.inputs import InputsUnavailableError

            if isinstance(exc, InputsUnavailableError):
                raise HTTPException(503, exc.code if hasattr(exc, "code") else "inventory_unavailable") from exc
            raise

    @router.put("/budget-caps")
    def put_budget(body: BudgetBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            cid = save_budget_cap(conn, body.period, body.scope, body.scope_key, body.amount, principal.subject, valid_from=body.valid_from)
        except PolicyError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        w = effective_weekly_budget(conn, today())
        return {"id": cid, "weekly_budget": None if w is None else str(w.quantize(Decimal("0.01")))}

    @router.get("/stocking/{variant_id}")
    def read_stocking(variant_id: int, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return get_stocking(conn, variant_id)

    @router.put("/stocking/{variant_id}")
    def put_stocking(variant_id: int, body: StockingBody, if_match: str | None = Header(default=None), conn: Connection = Depends(conn_dep),
                     principal: Any = Depends(require("buyer"))) -> Any:
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

    @router.get("/policy-overrides/recommendation/{variant_id}")
    def recommendation(variant_id: int, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        rec = recommended_safety_stock(conn, variant_id)
        return {"variant_id": variant_id, "safety_stock": rec, "effective": effective_for_variant(conn, variant_id, rec)}

    @router.post("/policy-overrides", status_code=201)
    def create_override(body: OverrideBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            r = request_override(conn, body.variant_id, body.field, body.requested_value, body.reason, principal.subject, recommended_safety_stock(conn, body.variant_id) if body.field == "safety_stock" else None)
        except OverrideRequestError as exc:
            raise HTTPException(409 if exc.code == "policy_override_pending" else 422, error_code(exc)) from exc
        return _json_override(r)

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
