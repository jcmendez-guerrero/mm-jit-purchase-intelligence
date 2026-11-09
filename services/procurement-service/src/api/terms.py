"""MMI 002 (T053): supplier terms and product-supplier overrides - history, If-Match concurrency, validation codes, effective view.

The If-Match header carries the version the editor last read. The first save of a record needs no header; once a version
exists it is required (428), and a stale one is refused with 412 and the current version so the editor can reload.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from costs.store import current as current_cost
from db.tables import product_refs
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from mmi_common.errors import error_code
from mmi_common.time import get_correlation_id
from proposals.publisher import terms_changed
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.engine import Connection
from terms.idempotency import IdempotencyError, remember, replay, request_hash, validate_key
from terms.overrides import (
    OverrideTerms,
    current_override,
    current_override_version,
    override_history,
    save_override,
    validate_override,
)
from terms.resolve import resolve_effective
from terms.service import (
    Discount,
    Terms,
    TermsConflict,
    TermsError,
    current_terms,
    current_version,
    history,
    save_terms,
    validate,
    version_statuses,
)


class DiscountBody(BaseModel):
    kind: str
    basis: str
    threshold: Decimal
    value: Decimal


class TermsBody(BaseModel):
    min_order_value: Decimal | None = None
    min_qty_for_delivery: int | None = None
    free_delivery_threshold: Decimal | None = None
    delivery_charge: Decimal | None = None
    order_days: list[int] = Field(default_factory=list, max_length=8)
    delivery_schedule: str | None = None
    lead_time_days: int | None = None
    order_cutoff_time: str | None = None
    delivery_weekdays: list[int] = Field(default_factory=list, max_length=8)
    discounts: list[DiscountBody] = Field(default_factory=list, max_length=10)
    payment_terms_days: int | None = None
    preferred: bool = False
    reliability: int | None = None
    disabled: bool = False
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


class OverrideBody(BaseModel):
    pack_multiple: int | None = None
    min_qty_units: int | None = None
    lead_time_days: int | None = None
    payment_terms_days: int | None = None
    preferred: bool | None = None
    reliability: int | None = None
    disabled: bool | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


def _money(v: Decimal | None) -> str | None:
    return None if v is None else str(v)


def terms_json(t: Terms) -> dict[str, Any]:
    return {"min_order_value": _money(t.min_order_value), "min_qty_for_delivery": t.min_qty_for_delivery, "free_delivery_threshold": _money(t.free_delivery_threshold),
            "delivery_charge": _money(t.delivery_charge), "order_days": list(t.order_days), "delivery_schedule": t.delivery_schedule,
            "lead_time_days": t.lead_time_days, "order_cutoff_time": t.order_cutoff_time, "delivery_weekdays": list(t.delivery_weekdays),
            "discounts": [{"kind": d.kind, "basis": d.basis, "threshold": str(d.threshold), "value": str(d.value)} for d in t.discounts],
            "payment_terms_days": t.payment_terms_days, "preferred": t.preferred, "reliability": t.reliability, "disabled": t.disabled,
            "valid_to": None if t.valid_to is None else t.valid_to.isoformat()}


def override_json(o: OverrideTerms | None) -> dict[str, Any] | None:
    return None if o is None else {f: getattr(o, f) for f in OverrideTerms.__dataclass_fields__}


def parse_if_match(header: str | None) -> int | None:
    if header is None:
        return None
    raw = header.strip().removeprefix("W/").strip('"')
    if not raw.isdigit():
        raise HTTPException(400, "request_invalid")
    return int(raw)


def _precondition(header: str | None, current: int) -> int | None:
    """None only for the very first save of a record; afterwards the caller must say which version it edited."""
    expected = parse_if_match(header)
    if expected is None and current > 0:
        raise HTTPException(428, "revision_required")
    return expected if expected is not None else 0


def _conflict(exc: TermsConflict) -> JSONResponse:
    return JSONResponse({"detail": exc.code, "current_version": exc.current_version}, status_code=412)


def _idempotency(conn: Connection, header: str | None, scope: str, target: str, if_match: str | None, body: BaseModel) -> tuple[str | None, str, JSONResponse | None]:
    """The checked key, the request hash, and the original result when this is a retry. Runs before the precondition: a retry's If-Match is already stale."""
    if header is None:
        return None, "", None
    try:
        key = validate_key(header)
        digest = request_hash(scope, target, if_match, body.model_dump(mode="json"))
        version = replay(conn, scope, key, digest)
    except IdempotencyError as exc:
        raise HTTPException(422, exc.code) from exc
    return key, digest, None if version is None else JSONResponse({"version": version}, headers={"Idempotent-Replay": "true"})


def _remember(conn: Connection, key: str | None, scope: str, digest: str, version: int, actor: str) -> None:
    if key is not None and not remember(conn, scope, key, digest, version, actor):
        raise HTTPException(412, "revision_conflict")      # a concurrent request with the same key won; raising rolls this save back, a retry replays the winner


def _parse_as_of(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(400, "request_invalid") from exc
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def register(router: APIRouter, conn_dep: Callable[..., Any], require: Callable[..., Any], app: FastAPI) -> None:
    def announce(conn: Connection, scope: str, key: str, version: int) -> None:
        """Queue the change notification in the same transaction. Without a configured blob writer there is nothing to announce to."""
        writer = getattr(app.state, "blob_writer", None)
        if writer is not None:
            terms_changed(conn, writer, scope, key, version, get_correlation_id())

    def buyer(request: Request, principal: Any = Depends(require())) -> Any:
        """Any signed-in caller first (so a refusal can name who tried, api/refusals.py), then the buyer role."""
        request.state.actor = principal.subject
        if "buyer" not in principal.roles:
            raise HTTPException(403, "auth_forbidden_role")
        return principal

    @router.get("/suppliers/{supplier_id}/terms")
    def get_terms(supplier_id: str, as_of: str | None = Query(default=None), conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        when = _parse_as_of(as_of)
        t = current_terms(conn, supplier_id, when)
        status = version_statuses(conn, supplier_id, when)
        return {"supplier_id": supplier_id, "version": current_version(conn, supplier_id), "current": None if t is None else terms_json(t),
                "history": [{"version": h["version"], "valid_from": h["valid_from"].isoformat(), "valid_to": None if h["valid_to"] is None else h["valid_to"].isoformat(),
                             "status": status[h["version"]], "source": h["source"], "reason": h["reason"], "changed_by": h["changed_by"],
                             "terms": terms_json(h["terms"])} for h in history(conn, supplier_id)]}

    @router.put("/suppliers/{supplier_id}/terms")
    def put_terms(supplier_id: str, body: TermsBody, if_match: str | None = Header(default=None), idempotency_key: str | None = Header(default=None),
                  conn: Connection = Depends(conn_dep), principal: Any = Depends(buyer)) -> Any:
        key, digest, replayed = _idempotency(conn, idempotency_key, "supplier_terms", supplier_id, if_match, body)
        if replayed is not None:
            return replayed
        terms = Terms(body.min_order_value, body.min_qty_for_delivery, body.free_delivery_threshold, body.delivery_charge, tuple(body.order_days), body.delivery_schedule,
                      body.lead_time_days, body.order_cutoff_time, tuple(body.delivery_weekdays), tuple(Discount(d.kind, d.basis, d.threshold, d.value) for d in body.discounts),
                      body.payment_terms_days, body.preferred, body.reliability, body.disabled, body.valid_to)
        try:
            validate(terms)                                          # report bad data before asking for the precondition
        except TermsError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        expected = _precondition(if_match, current_version(conn, supplier_id))
        try:
            version = save_terms(conn, supplier_id, terms, principal.subject, valid_from=body.valid_from, expected_version=expected, reason=body.reason)
        except TermsConflict as exc:
            return _conflict(exc)
        except TermsError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        _remember(conn, key, "supplier_terms", digest, version, principal.subject)
        announce(conn, "supplier_terms", supplier_id, version)
        return {"version": version}

    @router.get("/product-suppliers/{variant_id}/{supplier_id}/terms")
    def get_override(variant_id: int, supplier_id: str, as_of: str | None = Query(default=None), conn: Connection = Depends(conn_dep),
                     _p: Any = Depends(require())) -> dict[str, Any]:
        when = _parse_as_of(as_of)
        ref = conn.execute(select(product_refs.c.product_id).where(product_refs.c.variant_id == variant_id)).first()
        cost = None if ref is None else current_cost(conn, int(ref.product_id), supplier_id, variant_id) or current_cost(conn, int(ref.product_id), supplier_id)
        erp = None if cost is None else {"source": cost.source, "lead_time_days": cost.lead_time_days, "pack_size": cost.pack_size, "min_order_qty": cost.min_order_qty}
        eff = resolve_effective(conn, supplier_id, variant_id, when, erp)
        return {"variant_id": variant_id, "supplier_id": supplier_id, "version": current_override_version(conn, variant_id, supplier_id),
                "override": override_json(current_override(conn, variant_id, supplier_id, when)),
                "history": [{"version": h["version"], "valid_from": h["valid_from"].isoformat(), "source": h["source"], "reason": h["reason"],
                             "changed_by": h["changed_by"], "terms": override_json(h["terms"])} for h in override_history(conn, variant_id, supplier_id)],
                "effective": {"lead_time_days": eff.lead_time_days, "pack_multiple": eff.pack_multiple, "min_qty_units": eff.min_qty_units,
                              "payment_terms_days": eff.payment_terms_days, "preferred": eff.preferred, "reliability": eff.reliability, "disabled": eff.disabled,
                              "sources": eff.sources, "conflicts": list(eff.conflicts), "supplier_version": eff.supplier_version,
                              "override_version": eff.override_version, "flags": list(eff.flags)}}

    @router.put("/product-suppliers/{variant_id}/{supplier_id}/terms")
    def put_override(variant_id: int, supplier_id: str, body: OverrideBody, if_match: str | None = Header(default=None),
                     idempotency_key: str | None = Header(default=None), conn: Connection = Depends(conn_dep),
                     principal: Any = Depends(buyer)) -> Any:
        key, digest, replayed = _idempotency(conn, idempotency_key, "product_supplier_terms", f"{variant_id}:{supplier_id}", if_match, body)
        if replayed is not None:
            return replayed
        fields ={f: getattr(body, f) for f in OverrideTerms.__dataclass_fields__}
        try:
            validate_override(OverrideTerms(**fields))
        except TermsError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        expected = _precondition(if_match, current_override_version(conn, variant_id, supplier_id))
        try:
            version = save_override(conn, variant_id, supplier_id, OverrideTerms(**fields), principal.subject, valid_from=body.valid_from, valid_to=body.valid_to,
                                    expected_version=expected, reason=body.reason)
        except TermsConflict as exc:
            return _conflict(exc)
        except TermsError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        _remember(conn, key, "product_supplier_terms", digest, version, principal.subject)
        announce(conn, "product_supplier_terms", f"{variant_id}:{supplier_id}", version)
        return {"version": version}
