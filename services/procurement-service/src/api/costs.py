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
from costs.recargo import UnknownVatError, gross_from_net, load_table, net_from_gross
from costs.rules import CostRules, load_rules
from costs.store import CostError, NewCost, add_version, confirm_jump, cost_status, verify
from db.tables import erp_supplier_links, supplier_costs, suppliers
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from mmi_common.errors import error_code
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Connection, Engine
from terms.service import Terms, TermsError, current_terms, save_terms

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


class TermsBody(BaseModel):
    min_order_value: Decimal | None = None
    min_qty_for_delivery: int | None = None
    free_delivery_threshold: Decimal | None = None
    delivery_charge: Decimal | None = None
    order_days: list[int] = []
    delivery_schedule: str | None = None


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


def build_router(app: FastAPI) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def conn_dep(engine: Engine = Depends(get_engine)) -> Iterator[Connection]:
        with engine.begin() as conn:
            yield conn

    @router.get("/suppliers")
    def list_suppliers(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> list[dict[str, Any]]:
        out = []
        for s in conn.execute(select(suppliers).order_by(suppliers.c.name)).all():
            t = current_terms(conn, s.id)
            out.append({"id": s.id, "name": s.name, "terms": None if t is None else {
                "min_order_value": None if t.min_order_value is None else str(t.min_order_value), "min_qty_for_delivery": t.min_qty_for_delivery,
                "free_delivery_threshold": None if t.free_delivery_threshold is None else str(t.free_delivery_threshold),
                "delivery_charge": None if t.delivery_charge is None else str(t.delivery_charge), "order_days": list(t.order_days),
                "delivery_schedule": t.delivery_schedule}})
        return out

    @router.put("/suppliers/{supplier_id}/terms")
    def put_terms(supplier_id: str, body: TermsBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            version = save_terms(conn, supplier_id, Terms(body.min_order_value, body.min_qty_for_delivery, body.free_delivery_threshold,
                                                          body.delivery_charge, tuple(body.order_days), body.delivery_schedule), principal.subject)
        except TermsError as exc:
            raise HTTPException(422, error_code(exc)) from exc
        return {"version": version}

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

