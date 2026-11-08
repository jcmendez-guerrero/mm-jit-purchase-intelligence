"""T082: cost, supplier-terms and price-list endpoints (contracts/bff-api.openapi.yaml). Called by api-bff."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from audit.chain import append as audit
from audit.chain import verify_chain
from costs import price_import
from costs.directory import SqlProductDirectory
from costs.lot_costs import LotCostError, latest_by_lot, record_lot_cost, with_recargo
from costs.lot_lookup import LotLookupError
from costs.median_suggestion import request_median_write
from costs.recargo import UnknownVatError, gross_from_net, load_table, net_from_gross
from costs.rules import CostRules, load_rules
from costs.store import CostError, NewCost, add_version, confirm_jump, cost_status, verify
from db.tables import erp_supplier_links, product_refs, supplier_costs, suppliers
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from mmi_common.errors import error_code
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Connection, Engine
from terms.service import current_terms, current_version

from api.terms import register as register_terms_routes
from api.terms import terms_json

_engine: Engine | None = None
DISPLAY = Decimal("0.01")


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(os.environ["MMI_DATABASE_URL"], pool_pre_ping=True)
    return _engine


class CostEntry(BaseModel):
    product_id: int = Field(ge=1)
    supplier_id: str
    variant_id: int | None = Field(default=None, ge=1)
    amount: Decimal = Field(ge=0)
    includes_recargo: bool
    lead_time_days: int | None = Field(default=None, ge=0)
    min_order_qty: int | None = Field(default=None, ge=0)
    pack_size: int | None = Field(default=None, ge=1)


class LotCostEntry(BaseModel):
    variant_id: int = Field(ge=1)
    supplier_id: str
    lot: str = Field(min_length=1, max_length=60)
    amount: Decimal = Field(ge=0)
    includes_recargo: bool
    source: str = Field(pattern="^(buyer_entry|receipt_correction)$")
    quantity: int = Field(default=0, ge=0)


class CostUpdateBody(BaseModel):
    product_id: int = Field(ge=1)
    supplier_id: str


class VatBody(BaseModel):
    vat_rate: Decimal | None


def cost_json(row: Any, rules: CostRules, now: datetime) -> dict[str, Any]:
    s = lambda v: None if v is None else str(Decimal(str(v)).quantize(Decimal("0.0001")))  # noqa: E731
    return {
        "id": row.id, "product_id": row.product_id, "supplier_id": row.supplier_id, "variant_id": row.variant_id, "version": row.version,
        "cost_net": s(row.cost_net), "cost_with_recargo": s(row.cost_with_recargo), "recargo_rate": s(row.recargo_rate), "source": row.source,
        "verified_at": (row.verified_at if row.verified_at.tzinfo else row.verified_at.replace(tzinfo=UTC)).isoformat(),
        "status": cost_status(row, rules, now), "lead_time_days": row.lead_time_days, "min_order_qty": row.min_order_qty, "pack_size": row.pack_size,
    }


def _need_writer(app: FastAPI) -> Any:
    w = getattr(app.state, "blob_writer", None)
    if w is None:
        raise HTTPException(503, "not_configured")
    return w


def build_router(app: FastAPI) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def conn_dep(engine: Engine = Depends(get_engine)) -> Iterator[Connection]:
        with engine.begin() as conn:
            yield conn

    register_terms_routes(router, conn_dep, require, app)

    def lot_json(r: Any) -> dict[str, Any]:
        return {"id": r.id, "variant_id": r.variant_id, "supplier_id": r.supplier_id, "lot": r.lot, "unit_cost": str(Decimal(str(r.unit_cost)).quantize(Decimal("0.0001"))),
                "quantity": r.quantity, "source": r.source, "recorded_by": r.recorded_by, "recorded_at": r.recorded_at.isoformat()}

    @router.get("/lot-costs")
    def list_lot_costs(variant_id: int, supplier_id: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> list[dict[str, Any]]:
        return [lot_json(r) for r in latest_by_lot(conn, variant_id, supplier_id).values()]

    @router.post("/lot-costs", status_code=201)
    def add_lot_cost(body: LotCostEntry, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        """A buyer-entered opening entry or a correction on arrival. There is no endpoint for a free supplier-cost value: the ERP value is the median."""
        if conn.execute(select(suppliers.c.id).where(suppliers.c.id == body.supplier_id)).first() is None:
            raise HTTPException(422, "unknown_supplier")
        if conn.execute(select(product_refs.c.variant_id).where(product_refs.c.variant_id == body.variant_id)).first() is None:
            raise HTTPException(422, "unknown_variant")
        try:
            cost = with_recargo(conn, body.variant_id, body.amount, body.includes_recargo)
            row = record_lot_cost(conn, _need_writer(app), variant_id=body.variant_id, supplier_id=body.supplier_id, lot=body.lot, unit_cost=cost,
                                  source=body.source, actor=principal.subject, quantity=body.quantity)
        except LotCostError as exc:
            raise HTTPException(422, exc.code) from exc
        return lot_json(row)

    @router.post("/cost-updates", status_code=201)
    def request_cost_update(body: CostUpdateBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        """Builds the review request for the median of the lots in stock (looked up now). Nothing is sent to the ERP from here."""
        source = getattr(app.state, "lots_source", None)
        if source is None:
            raise HTTPException(503, "not_configured")
        try:
            res = request_median_write(conn, source, body.product_id, body.supplier_id, "buyer_entry", principal.subject, pvp_source=getattr(app.state, "pvp_source", None))
        except LotLookupError as exc:
            raise HTTPException(503, exc.code) from exc
        return {"status": res.status, "warnings": res.warnings, "request_id": None if res.request is None else res.request.id}

    @router.get("/suppliers")
    def list_suppliers(status: str | None = None, classification: str | None = None, q: str | None = None,
                       conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> list[dict[str, Any]]:
        from suppliers.service import list_suppliers as find_suppliers

        from api.suppliers import supplier_json

        out = []
        for s in find_suppliers(conn, status=status, classification=classification, q=q):
            t = current_terms(conn, s.id)
            out.append({**supplier_json(s), "supplier_version": int(s.version), "terms": None if t is None else terms_json(t), "version": current_version(conn, s.id)})
        return out

    @router.get("/costs")
    def list_costs(product_id: int | None = None, supplier_id: str | None = None, only_issues: bool = False,
                   conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> list[dict[str, Any]]:
        rules, now = load_rules(conn), datetime.now(UTC)
        q = select(supplier_costs).where(supplier_costs.c.superseded_by.is_(None)).order_by(supplier_costs.c.product_id, supplier_costs.c.supplier_id)
        if product_id is not None:
            q = q.where(supplier_costs.c.product_id == product_id)
        if supplier_id is not None:
            q = q.where(supplier_costs.c.supplier_id == supplier_id)
        rows = [cost_json(r, rules, now) for r in conn.execute(q).all()]
        return [r for r in rows if r["status"] != "ok"] if only_issues else rows

    @router.post("/costs", status_code=201)
    def enter_cost(body: CostEntry, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        if conn.execute(select(suppliers.c.id).where(suppliers.c.id == body.supplier_id)).first() is None:
            raise HTTPException(422, "unknown_supplier")
        directory, table, rules = SqlProductDirectory(conn), load_table(conn), load_rules(conn)
        vat = directory.vat_for_product(body.product_id)
        warnings: list[str] = []
        net = rate = None
        gross = body.amount
        try:
            pct = table.rate_for(vat)
            rate = pct / 100
            if body.includes_recargo:
                net = net_from_gross(body.amount, pct)
            else:
                net, gross = body.amount, gross_from_net(body.amount, pct)
        except UnknownVatError as exc:
            if not body.includes_recargo:
                raise HTTPException(422, "vat_unknown") from exc
            warnings.append("vat_unknown")
        link = conn.execute(select(erp_supplier_links.c.has_cost).where(erp_supplier_links.c.product_id == body.product_id,
                                                                         erp_supplier_links.c.supplier_id == body.supplier_id)).first()
        if link is None:
            erp, write_case = "no_link", "pending_link"          # keep locally; the buyer creates the link in the ERP
        elif not link.has_cost:
            erp, write_case = "link_without_cost", "missing_cost"  # may be written back after buyer review (T100)
        else:
            erp, write_case = "link_with_cost", None
        try:
            row = add_version(conn, NewCost(
                product_id=body.product_id, supplier_id=body.supplier_id, variant_id=body.variant_id, cost_with_recargo=gross, source="manual",
                actor=principal.subject, cost_net=net, recargo_rate=rate, entered_includes_recargo=body.includes_recargo, vat_rate_used=vat,
                pack_size=body.pack_size, lead_time_days=body.lead_time_days, min_order_qty=body.min_order_qty), rules)
        except CostError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        if row.jump_flag:
            warnings.append("abnormal_jump")
        return {"cost": cost_json(row, rules, datetime.now(UTC)), "erp_link": erp, "write_case": write_case, "warnings": warnings}

    @router.post("/costs/{cost_id}/verify", status_code=204)
    def verify_cost(cost_id: str, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> None:
        try:
            verify(conn, cost_id, principal.subject)
        except CostError as exc:
            raise HTTPException(404 if exc.code == "cost_not_found" else 409, error_code(exc)) from exc

    @router.post("/costs/{cost_id}/confirm-jump", status_code=204)
    def confirm(cost_id: str, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> None:
        try:
            confirm_jump(conn, cost_id, principal.subject)
        except CostError as exc:
            raise HTTPException(404 if exc.code == "cost_not_found" else 409, error_code(exc)) from exc

    @router.post("/costs/import")
    async def import_prices(supplier_id: str = Form(), file: UploadFile = File(), conn: Connection = Depends(conn_dep),
                            principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        if conn.execute(select(suppliers.c.id).where(suppliers.c.id == supplier_id)).first() is None:
            raise HTTPException(422, "unknown_supplier")
        data = await file.read(price_import.MAX_BYTES + 1)
        try:
            rows = price_import.read_rows(data, file.filename or "")
        except price_import.ImportFileError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        result = price_import.validate(rows, SqlProductDirectory(conn), load_table(conn))
        applied = price_import.apply(conn, result, supplier_id, principal.subject, load_rules(conn))
        audit(conn, principal.subject, "price_list.imported" if result.ok else "price_list.rejected", "supplier", supplier_id,
              after={"rows": len(rows), "applied": applied, "errors": len(result.errors)})
        return {"applied": applied, "rows": len(rows), "errors": [{"row": e.row, "column": e.column, "code": e.code} for e in result.errors]}

    @router.put("/products/{product_id}/vat")
    def set_vat(product_id: int, body: VatBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        if body.vat_rate is not None and not (Decimal(0) <= body.vat_rate <= Decimal(100)):
            raise HTTPException(422, "invalid_vat_rate")
        n = SqlProductDirectory(conn).set_vat(product_id, body.vat_rate)
        if n == 0:
            raise HTTPException(404, "unknown_product")
        audit(conn, principal.subject, "product.vat_set", "product", str(product_id), after={"vat_rate": None if body.vat_rate is None else str(body.vat_rate)})
        return {"product_id": product_id, "vat_rate": None if body.vat_rate is None else str(body.vat_rate)}

    @router.get("/audit/verify")
    def audit_verify(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        c = verify_chain(conn)
        return {"ok": c.ok, "checked": c.checked, "broken_at": c.broken_at, "reason": c.reason}

    return router

