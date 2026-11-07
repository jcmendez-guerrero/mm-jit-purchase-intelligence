"""T144: scenario routes. Creating needs an Idempotency-Key; promoting creates a normal draft proposal that someone else must approve."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Response
from mmi_common.errors import error_code
from proposals.inputs import InputsUnavailableError
from pydantic import BaseModel, Field
from scenarios import store as sc
from scenarios.engine import ScenarioError, ScenarioParams, SupplierDelta
from sqlalchemy.engine import Connection, Engine

from api.costs import get_engine
from api.proposals import _iso_week

CT = {"csv": "text/csv; charset=utf-8", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


class DeltaBody(BaseModel):
    min_order_value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    delivery_charge: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    free_delivery_threshold: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    pack_multiple: int | None = Field(default=None, ge=1, le=10_000)
    min_order_qty: int | None = Field(default=None, ge=0, le=1_000_000)


class ScenarioBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    budget: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    disabled_suppliers: list[str] = Field(default_factory=list, max_length=100)
    supplier_deltas: dict[str, DeltaBody] = Field(default_factory=dict, max_length=50)
    service_level_delta: Decimal = Field(default=Decimal(0), ge=Decimal("-0.4"), le=Decimal("0.4"))

    def params(self) -> ScenarioParams:
        return ScenarioParams(self.budget, tuple(self.disabled_suppliers), {sid: SupplierDelta(**d.model_dump()) for sid, d in self.supplier_deltas.items()}, self.service_level_delta)


class PromoteBody(BaseModel):
    week: str | None = Field(default=None, pattern=r"^\d{4}-W\d{2}$")


def build_router(app: FastAPI) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    def conn_dep(engine: Engine = Depends(get_engine)) -> Iterator[Connection]:
        with engine.begin() as conn:
            yield conn

    def base_inputs(conn: Connection) -> Any:
        provider = getattr(app.state, "inputs_provider", None)
        if provider is None:
            raise HTTPException(503, "not_configured")
        try:
            return provider.build(conn, datetime.now(UTC).date())
        except InputsUnavailableError as exc:
            raise HTTPException(503, exc.code) from exc

    def writer() -> Any:
        w = getattr(app.state, "blob_writer", None)
        if w is None:
            raise HTTPException(503, "not_configured")
        return w

    @router.post("/scenarios", status_code=201)
    def create(body: ScenarioBody, idempotency_key: str | None = Header(default=None), conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        if not idempotency_key or not (8 <= len(idempotency_key) <= 120):
            raise HTTPException(422, "idempotency_key_required")
        try:
            return sc.create(conn, writer(), body.name, body.params(), base_inputs(conn), principal.subject, f"{principal.subject}:{idempotency_key}")
        except ScenarioError as exc:
            raise HTTPException(422, error_code(exc)) from exc

    @router.get("/scenarios")
    def listing(conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        return {"scenarios": sc.listing(conn)}

    @router.get("/scenarios/{sid}")
    def read(sid: str, conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        try:
            return sc.get(conn, sid)
        except sc.ScenarioStateError as exc:
            raise HTTPException(404, error_code(exc)) from exc

    @router.post("/scenarios/{sid}/promote", status_code=201)
    def promote(sid: str, body: PromoteBody | None = None, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("buyer"))) -> dict[str, Any]:
        try:
            return sc.promote(conn, sid, base_inputs(conn), principal.subject, (body.week if body and body.week else None) or _iso_week(datetime.now(UTC).date()))
        except sc.ScenarioStateError as exc:
            raise HTTPException(404 if exc.code == "unknown_scenario" else 409, error_code(exc)) from exc
        except ScenarioError as exc:
            raise HTTPException(422, error_code(exc)) from exc

    @router.get("/scenarios/{sid}/export")
    def export(sid: str, format: str = Query(pattern="^(csv|xlsx)$"), conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> Response:
        try:
            sc.get(conn, sid)
        except sc.ScenarioStateError as exc:
            raise HTTPException(404, error_code(exc)) from exc
        return Response(sc.export(conn, sid, format), media_type=CT[format], headers={"Content-Disposition": f'attachment; filename="escenario.{format}"'})

    return router
