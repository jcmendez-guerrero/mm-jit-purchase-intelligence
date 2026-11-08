"""T050: supplier management API (contracts/suppliers-api.md). Buyers and admins write; every signed-in role reads.

Nothing here talks to the ERP: links for a supplier without an ERP counterpart report ``pending_link``. Money travels as decimal strings.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Iterator
from decimal import Decimal, InvalidOperation
from typing import Any

from costs.recargo import load_table
from costs.rules import load_rules
from db.tables import supplier_review_items
from fastapi import APIRouter, Depends, FastAPI, File, Header, HTTPException, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine, Row
from suppliers.bulk import BulkError, apply_batch, parse_assignment_file, preview_batch
from suppliers.links import LinkError, LinkInput, list_links, put_link, remove_link
from suppliers.merge import MergeError, merge_suppliers, resolve_review_item
from suppliers.service import (
    SupplierConflict,
    SupplierError,
    SupplierInput,
    create_supplier,
    deactivate_supplier,
    get_supplier,
    reactivate_supplier,
    update_supplier,
)

from api.costs import get_engine
from api.terms import parse_if_match

MAX_UPLOAD = 5 * 1024 * 1024
STATUS = {
    "supplier_not_found": 404, "supplier_possible_duplicate": 409, "supplier_invalid": 422, "supplier_deactivated": 409, "supplier_merged": 409,
    "link_sku_unknown": 422, "link_cost_invalid": 422, "link_currency_mismatch": 422, "vat_unknown": 422, "link_not_found": 404,
    "bulk_criteria_invalid": 422, "bulk_preview_stale": 409, "bulk_conflicts_unresolved": 409, "bulk_file_invalid": 422,
    "merge_same_supplier": 422, "merge_currency_mismatch": 409, "merge_open_lines": 409, "review_item_not_found": 404, "review_item_closed": 409,
    "request_invalid": 422,
}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SupplierBody(Strict):
    name: str
    fiscal_type: str
    country: str
    currency: str
    payment_terms_days: int | None = None
    order_channel: str | None = None
    classification: str = "purchasing"


class SupplierPatch(Strict):
    name: str | None = None
    fiscal_type: str | None = None
    country: str | None = None
    currency: str | None = None
    payment_terms_days: int | None = None
    order_channel: str | None = None
    classification: str | None = None


class DeactivateBody(Strict):
    confirm: bool = False


class LinkBody(Strict):
    cost: str | None = Field(default=None, pattern=r"^[0-9]+(\.[0-9]{1,4})?$")
    includes_recargo: bool = True
    cost_source: str = "manual"
    pack_size: int | None = Field(default=None, ge=1)
    min_qty: int | None = Field(default=None, ge=1)


class BulkPreviewBody(Strict):
    skus: list[str] | None = None
    q: str | None = None


class BulkApplyBody(Strict):
    batch_id: str
    skip_conflicts: bool = False


class ResolveBody(Strict):
    decision: str
    merge_into: str | None = None


class MergeBody(Strict):
    merge_into: str
    confirm: bool = False


def supplier_json(r: Row[Any]) -> dict[str, Any]:
    iso = lambda ts: None if ts is None else (ts.isoformat() if ts.tzinfo else ts.replace(tzinfo=None).isoformat() + "Z")  # noqa: E731
    return {"id": r.id, "external_contact_id": r.external_contact_id, "name": r.name, "status": r.status, "classification": r.classification, "origin": r.origin,
            "erp_link_state": r.erp_link_state, "fiscal_type": r.fiscal_type, "country": r.country, "currency": r.currency, "payment_terms_days": r.payment_terms_days,
            "order_channel": r.order_channel, "has_note": bool(r.has_note), "version": int(r.version), "merged_into": r.merged_into,
            "created_at": iso(r.created_at), "updated_at": iso(r.updated_at)}


def _error(exc: Exception) -> JSONResponse:
    code = getattr(exc, "code", "request_invalid")
    body: dict[str, Any] = {"detail": code}
    for attr in ("field", "duplicates", "open_lines", "current_version"):
        v = getattr(exc, attr, None)
        if v:
            body[attr] = v
    return JSONResponse(body, status_code=412 if isinstance(exc, SupplierConflict) else STATUS.get(code, 400))


def build_router(app: FastAPI) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()
    read = require()
    write_dep = require()

    def writer(principal: Any = Depends(write_dep)) -> Any:
        if not ({"buyer", "admin"} & set(principal.roles)):
            raise HTTPException(403, "auth_forbidden_role")
        return principal

    def conn_dep(engine: Engine = Depends(get_engine)) -> Iterator[Connection]:
        with engine.begin() as conn:
            yield conn

    def refresher(conn: Connection) -> Callable[[], None] | None:
        provider = getattr(app.state, "inputs_provider", None)
        if provider is None:
            return None

        def refresh() -> None:
            from proposals.inputs import refresh_product_refs

            refresh_product_refs(conn, provider.stock.fetch().get("variants", []))

        return refresh

    # ---- review items first: a literal path must win over /suppliers/{supplier_id}
    @router.get("/suppliers/review-items")
    def review_items(status: str = Query(default="open"), conn: Connection = Depends(conn_dep), _p: Any = Depends(read)) -> list[dict[str, Any]]:
        q = select(supplier_review_items).order_by(supplier_review_items.c.created_at.desc())
        if status != "all":
            q = q.where(supplier_review_items.c.status == status)
        return [{"id": r.id, "kind": r.kind, "supplier_id": r.supplier_id, "detail": r.detail, "status": r.status, "created_at": r.created_at.isoformat()}
                for r in conn.execute(q.limit(500)).all()]

    @router.post("/suppliers/review-items/{item_id}/resolve", status_code=204, response_model=None)
    def resolve(item_id: str, body: ResolveBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(writer)) -> Any:
        try:
            resolve_review_item(conn, item_id, body.decision, principal.subject, merge_into=body.merge_into)
        except (MergeError, SupplierError) as exc:
            return _error(exc)
        return Response(status_code=204)

    @router.post("/suppliers", status_code=201)
    def create(body: SupplierBody, confirm_duplicate: bool = Query(default=False), conn: Connection = Depends(conn_dep), principal: Any = Depends(writer)) -> Any:
        try:
            row = create_supplier(conn, SupplierInput(**body.model_dump()), principal.subject, confirm_duplicate=confirm_duplicate)
        except SupplierError as exc:
            return _error(exc)
        return supplier_json(row)

    @router.get("/suppliers/{supplier_id}")
    def detail(supplier_id: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(read)) -> Any:
        try:
            return supplier_json(get_supplier(conn, supplier_id))
        except SupplierError as exc:
            return _error(exc)

    @router.patch("/suppliers/{supplier_id}")
    def patch(supplier_id: str, body: SupplierPatch, confirm_duplicate: bool = Query(default=False), if_match: str | None = Header(default=None),
              conn: Connection = Depends(conn_dep), principal: Any = Depends(writer)) -> Any:
        expected = parse_if_match(if_match)
        if expected is None:
            raise HTTPException(428, "revision_required")
        changes = body.model_dump(exclude_unset=True)
        try:
            return supplier_json(update_supplier(conn, supplier_id, changes, principal.subject, expected, confirm_duplicate=confirm_duplicate))
        except (SupplierError, SupplierConflict) as exc:
            return _error(exc)

    @router.post("/suppliers/{supplier_id}/deactivate")
    def deactivate(supplier_id: str, body: DeactivateBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(writer)) -> Any:
        try:
            return deactivate_supplier(conn, supplier_id, principal.subject, confirm=body.confirm)
        except SupplierError as exc:
            return _error(exc)

    @router.post("/suppliers/{supplier_id}/reactivate")
    def reactivate(supplier_id: str, conn: Connection = Depends(conn_dep), principal: Any = Depends(writer)) -> Any:
        try:
            return supplier_json(reactivate_supplier(conn, supplier_id, principal.subject))
        except SupplierError as exc:
            return _error(exc)

    @router.post("/suppliers/{supplier_id}/merge")
    def merge(supplier_id: str, body: MergeBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(writer)) -> Any:
        try:
            return merge_suppliers(conn, supplier_id, body.merge_into, principal.subject, confirm=body.confirm)
        except MergeError as exc:
            return _error(exc)

    @router.get("/suppliers/{supplier_id}/links")
    def links(supplier_id: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(read)) -> Any:
        try:
            get_supplier(conn, supplier_id)
        except SupplierError as exc:
            return _error(exc)
        return list_links(conn, supplier_id)

    @router.put("/suppliers/{supplier_id}/links/{sku:path}")
    def put(supplier_id: str, sku: str, body: LinkBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(writer)) -> Any:
        try:
            amount = None if body.cost is None else Decimal(body.cost)
            res = put_link(conn, supplier_id, sku, LinkInput(cost=amount, includes_recargo=body.includes_recargo, source=body.cost_source, pack_size=body.pack_size,
                                                             min_qty=body.min_qty), principal.subject, load_rules(conn), load_table(conn), refresh=refresher(conn))
        except (LinkError, SupplierError, InvalidOperation) as exc:
            return _error(exc if not isinstance(exc, InvalidOperation) else LinkError("link_cost_invalid"))
        return {"cost_id": res.cost.id, "version": int(res.cost.version), "cost": str(Decimal(str(res.cost.cost_with_recargo)).quantize(Decimal("0.0001"))),
                "source": res.cost.source, "erp_link": res.erp_link, "write_case": res.write_case, "warnings": res.warnings}

    @router.delete("/suppliers/{supplier_id}/links/{sku:path}", status_code=204, response_model=None)
    def delete(supplier_id: str, sku: str, conn: Connection = Depends(conn_dep), principal: Any = Depends(writer)) -> Any:
        try:
            remove_link(conn, supplier_id, sku, principal.subject)
        except LinkError as exc:
            return _error(exc)
        return Response(status_code=204)

    @router.post("/suppliers/{supplier_id}/links/bulk/preview")
    def bulk_preview(supplier_id: str, body: BulkPreviewBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(writer)) -> Any:
        criteria = {k: v for k, v in body.model_dump().items() if v is not None}
        try:
            return preview_batch(conn, supplier_id, criteria, principal.subject)
        except (BulkError, SupplierError) as exc:
            return _error(exc)

    @router.post("/suppliers/{supplier_id}/links/bulk/apply")
    def bulk_apply(supplier_id: str, body: BulkApplyBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(writer)) -> Any:
        try:
            return apply_batch(conn, body.batch_id, principal.subject, load_rules(conn), load_table(conn), skip_conflicts=body.skip_conflicts, refresh=refresher(conn))
        except (BulkError, LinkError, SupplierError) as exc:
            return _error(exc)

    @router.post("/links/bulk/file")
    async def bulk_file(file: UploadFile = File(...), conn: Connection = Depends(conn_dep), _p: Any = Depends(writer)) -> Any:
        name = (file.filename or "").lower()
        if not name.endswith((".csv", ".txt")):
            return JSONResponse({"detail": "import_type_not_allowed"}, status_code=415)
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            return JSONResponse({"detail": "import_file_too_large"}, status_code=413)
        try:
            return parse_assignment_file(conn, io.BytesIO(data).read())
        except BulkError as exc:
            return _error(exc)

    return router
