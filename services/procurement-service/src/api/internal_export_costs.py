"""T096: flag-guarded internal route the local loader uses to refresh export costs (FR-037, FR-039).

Mounted only when ``MMI_LOCAL_LOADER=1`` and the environment is not production or staging; requires the ``local-loader`` role
(an audience-scoped service identity). Money travels as decimal strings, never floats.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.engine import Engine
from suppliers.export_costs import upsert_export_costs

from api.costs import get_engine

MONEY = r"^-?[0-9]+(\.[0-9]{1,4})?$"
NON_NEGATIVE = r"^[0-9]+(\.[0-9]{1,4})?$"


def enabled(env: Mapping[str, str] | None = None) -> bool:
    e = os.environ if env is None else env
    return e.get("MMI_LOCAL_LOADER") == "1" and e.get("MMI_ENV", "") not in {"prod", "staging"}


class ExportCostRow(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sku: str = Field(min_length=1, max_length=60)
    export_cost: str | None = Field(default=None, pattern=NON_NEGATIVE)
    pvp_gross: str | None = Field(default=None, pattern=NON_NEGATIVE)
    tax_rate: str | None = Field(default=None, pattern=NON_NEGATIVE)
    tax_included: bool = False
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")


class ExportCostsBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    load_run_id: str | None = Field(default=None, max_length=36)
    rows: list[ExportCostRow] = Field(max_length=20000)


def _dec(v: str | None) -> Decimal | None:
    return None if v is None else Decimal(v)


def build_router(app: FastAPI) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter(prefix="/internal")

    @router.post("/export-costs")
    def put_export_costs(body: ExportCostsBody, engine: Engine = Depends(get_engine), _p: Any = Depends(require("local-loader"))) -> dict[str, int]:
        rows = [{"sku": r.sku, "export_cost": _dec(r.export_cost), "pvp_gross": _dec(r.pvp_gross), "tax_rate": _dec(r.tax_rate),
                 "tax_included": r.tax_included, "currency": r.currency} for r in body.rows]
        with engine.begin() as conn:
            return {"upserted": upsert_export_costs(conn, rows, body.load_run_id, datetime.now(UTC))}

    return router
