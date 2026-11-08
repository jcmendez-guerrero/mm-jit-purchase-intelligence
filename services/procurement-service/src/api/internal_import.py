"""T063: flag-guarded internal routes the local loader uses to import suppliers and to link products named in the inventory export.

Mounted only when ``MMI_LOCAL_LOADER=1`` and the environment is not production or staging; requires the ``local-loader`` role (an audience-scoped
service identity). Rows carry no tax ids, bank data, contacts or notes: unknown fields are refused.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from costs.recargo import load_table
from costs.rules import load_rules
from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.engine import Connection, Engine
from suppliers.importer import import_suppliers
from suppliers.links import auto_link

from api.costs import get_engine
from api.internal_export_costs import enabled  # noqa: F401 - same guard for every internal local-loader route


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SupplierRowIn(Strict):
    external_contact_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    fiscal_type: str = Field(pattern=r"^(national|intracommunity|foreign)$")
    country: str = Field(pattern=r"^[A-Z]{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    terms_unparsed: bool = False
    has_note: bool = False


class ImportBody(Strict):
    load_run_id: str | None = Field(default=None, max_length=36)
    rows: list[SupplierRowIn] = Field(max_length=5000)


class LinkRowIn(Strict):
    sku: str = Field(min_length=1, max_length=60)
    supplier_name: str = Field(min_length=1, max_length=200)


class AutoLinkBody(Strict):
    rows: list[LinkRowIn] = Field(max_length=20000)


def build_router(app: FastAPI) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter(prefix="/internal")

    def conn_dep(engine: Engine = Depends(get_engine)) -> Iterator[Connection]:
        with engine.begin() as conn:
            yield conn

    @router.post("/suppliers/import")
    def import_rows(body: ImportBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("local-loader"))) -> dict[str, int]:
        return import_suppliers(conn, [r.model_dump() for r in body.rows], principal.subject)

    @router.post("/links/auto")
    def link_rows(body: AutoLinkBody, conn: Connection = Depends(conn_dep), principal: Any = Depends(require("local-loader"))) -> dict[str, int]:
        provider = getattr(app.state, "inputs_provider", None)

        def refresh() -> None:
            from proposals.inputs import refresh_product_refs

            refresh_product_refs(conn, provider.stock.fetch().get("variants", []))

        return auto_link(conn, [r.model_dump() for r in body.rows], principal.subject, load_rules(conn), load_table(conn), refresh=refresh if provider else None)

    return router
