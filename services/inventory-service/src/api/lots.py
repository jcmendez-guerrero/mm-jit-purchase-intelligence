"""T058: lots in stock, per variant, for the supplier-cost median (FR-040). Read-only; callers pass the audience-scoped service identity."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from db.tables import stock_lots, variants
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

MAX_VARIANTS = 200
PRICE_STALE_AFTER = timedelta(days=7)          # FR-043: a price last confirmed by a sync longer ago than this blocks the margin check


def build_lots_router(app: FastAPI, conn_dep: Callable[..., Connection]) -> APIRouter:
    require: Callable[..., Any] = app.state.require_roles
    router = APIRouter()

    @router.get("/lots/in-stock")
    def lots_in_stock(variant_ids: str = Query(min_length=1, max_length=2000), conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """Remaining quantity per (variant, batch) summed over warehouses. Lots without a batch number are reported with ``lot: null``."""
        try:
            ids = sorted({int(x) for x in variant_ids.split(",") if x.strip()})
        except ValueError as exc:
            raise HTTPException(422, "invalid_variant_ids") from exc
        if not ids or len(ids) > MAX_VARIANTS or any(i < 1 for i in ids):
            raise HTTPException(422, "invalid_variant_ids")
        rows = conn.execute(
            select(stock_lots.c.variant_id, stock_lots.c.batch_number, func.sum(stock_lots.c.quantity).label("qty"), func.max(stock_lots.c.seen_at).label("seen_at"))
            .where(stock_lots.c.variant_id.in_(ids), stock_lots.c.quantity > 0)
            .group_by(stock_lots.c.variant_id, stock_lots.c.batch_number).order_by(stock_lots.c.variant_id, stock_lots.c.batch_number)).all()
        return {"lots": [{"variant_id": r.variant_id, "lot": r.batch_number, "quantity": int(r.qty), "seen_at": r.seen_at.isoformat() if r.seen_at else None} for r in rows]}

    @router.get("/pvp")
    def pvp(variant_ids: str = Query(min_length=1, max_length=2000), conn: Connection = Depends(conn_dep), _p: Any = Depends(require())) -> dict[str, Any]:
        """Selling price (PVP) per variant: the variant price synchronised from the ERP (decided 2026-11-06). It is treated as net of VAT for
        every product, so it is returned as is, with the time a sync last confirmed it and whether that is stale (over 7 days; no time counts as stale).
        Variants without a price are omitted: the caller reports the margin as unavailable."""
        try:
            ids = sorted({int(x) for x in variant_ids.split(",") if x.strip()})
        except ValueError as exc:
            raise HTTPException(422, "invalid_variant_ids") from exc
        if not ids or len(ids) > MAX_VARIANTS or any(i < 1 for i in ids):
            raise HTTPException(422, "invalid_variant_ids")
        rows = conn.execute(select(variants.c.external_id, variants.c.price, variants.c.price_confirmed_at)
                            .where(variants.c.external_id.in_(ids), variants.c.price.is_not(None), variants.c.price > 0).order_by(variants.c.external_id)).all()
        now = datetime.now(UTC)
        out = []
        for r in rows:
            at = None if r.price_confirmed_at is None else (r.price_confirmed_at if r.price_confirmed_at.tzinfo else r.price_confirmed_at.replace(tzinfo=UTC))
            age = None if at is None else now - at
            out.append({"variant_id": r.external_id, "pvp": str(r.price), "source": "variant_price", "as_of": None if at is None else at.isoformat(),
                        "age_days": None if age is None else max(0, age.days), "stale": age is None or age > PRICE_STALE_AFTER})
        return {"prices": out}

    return router
