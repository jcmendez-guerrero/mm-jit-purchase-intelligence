"""T105: proposal, order and cost-write endpoints (contracts/bff-api.openapi.yaml). Called by api-bff on behalf of the user."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Protocol

from approvals.workflow import ApprovalError, UserDirectory, decide, is_approval_valid, submit
from costs.writes import WriteError, approve_write, cancel_write, list_visible, writer_view
from db.tables import approvals, proposal_lines, proposals, supplier_order_groups
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Response
from mmi_common.errors import error_code
from mmi_common.time import get_correlation_id, set_correlation_id
from orders.confirm import ConfirmLine, OrderError, confirm_order
from proposals.edit import ConcurrencyError, EditError, ProposalStateError, edit_line
from proposals.export import ExportError, export_proposal
from proposals.generate import ProposalConflictError, generate, store
from proposals.inputs import InputsUnavailableError
from proposals.model import ProposalInputs
from proposals.publisher import BlobWriter, proposal_generated
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from users.directory import DirectoryError, set_roles

from api.costs import get_engine


class InputsProvider(Protocol):
    def build(self, conn: Connection, today: date) -> ProposalInputs: ...


class LineEdit(BaseModel):
    qty: int | None = Field(default=None, ge=0)
    supplier_id: str | None = None


class ConfirmLineBody(BaseModel):
    variant_id: int = Field(ge=1)
    qty: int = Field(ge=0)
    cost_with_recargo: Decimal = Field(ge=0)


class OrderConfirmation(BaseModel):
    lines: list[ConfirmLineBody] = Field(min_length=1)
    erp_purchase_ref: int | None = None


USER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@:+-]{0,119}")


class RolesBody(BaseModel):
    roles: list[str] = Field(max_length=8)
    active: bool = True
    revision: int | None = Field(default=None, ge=0)        # the BFF role revision; stale mirrors are ignored


class WriteApproval(BaseModel):
    acknowledge_variant_conflict: bool = False


def _iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _need(app: FastAPI, name: str) -> Any:
    obj = getattr(app.state, name, None)
    if obj is None:
        raise HTTPException(503, "not_configured")
    return obj


def _version(if_match: str | None, current: int) -> int:
    if if_match is None:
        return current
    try:
        return int(if_match.strip('"'))
    except ValueError as exc:
        raise HTTPException(400, "invalid_if_match") from exc


def proposal_json(conn: Connection, p: Any) -> dict[str, Any]:
    lines = conn.execute(select(proposal_lines).where(proposal_lines.c.proposal_id == p.id).order_by(proposal_lines.c.variant_id)).all()
    groups = conn.execute(select(supplier_order_groups).where(supplier_order_groups.c.proposal_id == p.id).order_by(supplier_order_groups.c.supplier_id)).all()
    last = conn.execute(select(approvals).where(approvals.c.proposal_id == p.id).order_by(approvals.c.id.desc()).limit(1)).first()
    s = lambda v: str(Decimal(str(v)))  # noqa: E731
    return {
        "id": p.id, "week": p.week, "status": p.status, "version": p.version, "created_by": p.created_by, "last_edited_by": p.last_edited_by,
        "inputs_hash": p.inputs_hash, "rule_versions": p.rule_versions, "solver_status": p.solver_status, "flags": p.flags,
        "approval": None if last is None else {"approver": last.approver_id, "decision": last.decision, "version": last.proposal_version, "valid": is_approval_valid(conn, p.id)},
        "lines": [{"id": r.id, "variant_id": r.variant_id, "product_id": r.product_id, "supplier_id": r.supplier_id, "qty": r.qty,
                   "unit_cost_with_recargo": s(r.unit_cost_with_recargo), "line_total": s(r.line_total), "forecast_or_policy": r.forecast_or_policy,
                   "safety_stock": r.safety_stock, "constraints_applied": r.constraints_applied, "risk": r.risk, "confidence": r.confidence,
                   "explanation": r.explanation, "alternatives_compared": r.alternatives_compared, "manual_override": r.manual_override, "topup": r.topup} for r in lines],
        "supplier_groups": [{"supplier_id": g.supplier_id, "subtotal": s(g.subtotal), "delivery_charge": s(g.delivery_charge), "total_cost": s(g.total_cost),
                             "expected_delivery_date": g.expected_delivery_date.isoformat() if g.expected_delivery_date else None, "minimum_status": g.minimum_status,
                             "free_delivery": g.free_delivery, "shortfall_options": g.shortfall_options} for g in groups],
    }


def build_router(app: FastAPI) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def conn_dep(engine: Engine = Depends(get_engine)) -> Iterator[Connection]:
        with engine.begin() as conn:
            yield conn

    def get_proposal(conn: Connection, proposal_id: str) -> Any:
        p = conn.execute(select(proposals).where(proposals.c.id == proposal_id)).first()
        if p is None:
            raise HTTPException(404, "unknown_proposal")
        return p

    @router.get("/proposals")
    def list_proposals(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> list[dict[str, Any]]:
        return [{"id": p.id, "week": p.week, "status": p.status, "version": p.version, "created_by": p.created_by, "updated_at": p.updated_at.isoformat()}
                for p in conn.execute(select(proposals).order_by(proposals.c.created_at.desc())).all()]

    @router.post("/proposals", status_code=202)
    def generate_proposal(conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        provider: InputsProvider = _need(app, "inputs_provider")
        writer: BlobWriter = _need(app, "blob_writer")
        today = datetime.now(UTC).date()
        try:
            inputs = provider.build(conn, today)
        except InputsUnavailableError as exc:
            raise HTTPException(503, exc.code) from exc
        try:
            pid = store(conn, generate(inputs), principal.subject, _iso_week(today), inputs.budget)
        except ProposalConflictError as exc:
            raise HTTPException(409, error_code(exc)) from exc
        p = get_proposal(conn, pid)
        proposal_generated(conn, writer, pid, p.week, p.version, get_correlation_id() or set_correlation_id())
        return {"id": pid, "status": p.status, "version": p.version}

    @router.get("/proposals/{proposal_id}")
    def read_proposal(proposal_id: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return proposal_json(conn, get_proposal(conn, proposal_id))

    @router.patch("/proposals/{proposal_id}/lines/{line_id}")
    def patch_line(proposal_id: str, line_id: str, body: LineEdit, if_match: str | None = Header(default=None), conn: Connection = Depends(conn_dep),
                   principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        p = get_proposal(conn, proposal_id)
        line = conn.execute(select(proposal_lines).where(proposal_lines.c.id == line_id, proposal_lines.c.proposal_id == proposal_id)).first()
        if line is None:
            raise HTTPException(404, "unknown_line")
        try:
            res = edit_line(conn, proposal_id, line.variant_id, _version(if_match, p.version), principal.subject, qty=body.qty, supplier_id=body.supplier_id)
        except ConcurrencyError as exc:
            raise HTTPException(409, error_code(exc)) from exc
        except ProposalStateError as exc:
            raise HTTPException(409, error_code(exc)) from exc
        except EditError as exc:
            raise HTTPException(422, exc.code) from exc
        out = proposal_json(conn, get_proposal(conn, proposal_id))
        out["warnings"] = res.warnings
        return out

    @router.post("/proposals/{proposal_id}/submit")
    def submit_proposal(proposal_id: str, if_match: str | None = Header(default=None), conn: Connection = Depends(conn_dep),
                        principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        directory = _need(app, "user_directory")
        users: UserDirectory = directory.bind(conn) if hasattr(directory, "bind") else directory
        p = get_proposal(conn, proposal_id)
        try:
            submit(conn, proposal_id, principal.subject, _version(if_match, p.version), users)
        except (ConcurrencyError, ProposalStateError) as exc:
            raise HTTPException(409, error_code(exc)) from exc
        except ApprovalError as exc:
            raise HTTPException(409, exc.code) from exc
        return {"status": "submitted"}

    @router.post("/proposals/{proposal_id}/approve")
    def approve_proposal(proposal_id: str, if_match: str | None = Header(default=None), conn: Connection = Depends(conn_dep),
                         principal: Any = Depends(require("approver"))) -> dict[str, Any]:
        p = get_proposal(conn, proposal_id)
        try:
            decide(conn, proposal_id, principal, _version(if_match, p.version))
        except (ConcurrencyError, ProposalStateError) as exc:
            raise HTTPException(409, error_code(exc)) from exc
        except ApprovalError as exc:
            raise HTTPException(403, exc.code) from exc
        return {"status": "approved"}

    @router.get("/proposals/{proposal_id}/export")
    def export(proposal_id: str, format: str = Query(pattern="^(csv|xlsx)$"), supplier_id: str | None = None, conn: Connection = Depends(conn_dep),
              principal: Any = Depends(require("buyer"))) -> Response:
        try:
            data = export_proposal(conn, proposal_id, format, principal.subject, supplier_id)
        except ExportError as exc:
            raise HTTPException(409 if exc.code == "proposal_not_approved" else 404, exc.code) from exc
        media = "text/csv; charset=utf-8" if format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="pedido-{proposal_id[:8]}.{format}"'})

    @router.post("/proposals/{proposal_id}/orders/{supplier_id}/confirm", status_code=201)
    def confirm(proposal_id: str, supplier_id: str, body: OrderConfirmation, conn: Connection = Depends(conn_dep),
                principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        writer: BlobWriter = _need(app, "blob_writer")
        try:
            res = confirm_order(conn, proposal_id, supplier_id, [ConfirmLine(x.variant_id, x.qty, x.cost_with_recargo) for x in body.lines],
                                principal.subject, writer, erp_purchase_ref=body.erp_purchase_ref)
        except (OrderError, ProposalStateError) as exc:
            raise HTTPException(409, error_code(exc)) from exc
        return {"order_id": res.order_id, "warnings": res.warnings,
                "cost_writes": [{"id": w.request.id, "status": w.status, "warnings": w.warnings} for w in res.cost_writes if w.request is not None]}

    def write_json(r: Any) -> dict[str, Any]:
        return {"id": r.id, "cost_id": r.cost_id, "product_id": r.product_id, "supplier_id": r.supplier_id, "trigger": r.trigger,
                "proposed_value": str(Decimal(str(r.proposed_value))), "previous_siweb_value": None if r.previous_siweb_value is None else str(Decimal(str(r.previous_siweb_value))),
                "status": r.status, "attempts": r.attempts, "last_error": r.last_error}

    @router.get("/cost-writes")
    def cost_writes(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> list[dict[str, Any]]:
        return [write_json(r) for r in list_visible(conn)]

    @router.post("/cost-writes/{request_id}/approve", status_code=202)
    def approve_cost_write(request_id: str, body: WriteApproval | None = None, conn: Connection = Depends(conn_dep),
                           principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        writer: BlobWriter = _need(app, "blob_writer")
        try:
            r = approve_write(conn, request_id, principal, writer, bool(body and body.acknowledge_variant_conflict))
        except WriteError as exc:
            raise HTTPException(403 if exc.code in ("mfa_required", "not_a_buyer") else 409, exc.code) from exc
        return write_json(r)

    @router.post("/cost-writes/{request_id}/cancel", status_code=204)
    def cancel(request_id: str, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> None:
        try:
            cancel_write(conn, request_id, principal.subject)
        except WriteError as exc:
            raise HTTPException(409, exc.code) from exc

    @router.get("/internal/cost-writes/{request_id}")
    def internal_write(request_id: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(require("cost-writer"))) -> dict[str, Any]:
        view = writer_view(conn, request_id)
        if view is None:
            raise HTTPException(404, "write_request_not_released")
        return view

    @router.put("/internal/users/{user_id}/roles")
    def mirror_roles(user_id: str, body: RolesBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("bff"))) -> dict[str, Any]:
        if not USER_ID.fullmatch(user_id):
            raise HTTPException(422, "invalid_user_id")
        try:
            applied = set_roles(conn, user_id, body.roles, principal.subject, body.active, revision=body.revision)
        except DirectoryError as exc:
            raise HTTPException(422, "unknown_role") from exc
        return {"user_id": user_id, "roles": sorted(set(body.roles)), "active": body.active, "applied": applied}

    return router
