"""Feature 014 (FR-008): one product's page of the dashboard, found by SKU. Read-only; the SKU is resolved to the internal id here and the id never leaves.

Cost fields are built only for roles that may see money (the caller passes ``with_cost``), so a viewer's response has no cost key at all rather than a hidden one.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from db.tables import demand_observations, stock_lots, variants
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from dashboard.kpis import (
    FORECAST_DAYS,
    Filters,
    ForecastMeans,
    _costs,
    _on_hand,
    coverage_by_variant,
)

DEMAND_DAYS = 28


class SkuNotFound(Exception):
    code = "sku_not_found"


def _band(expiry: date | None, today: date) -> str:
    if expiry is None:
        return "none"
    if expiry < today:
        return "expired"
    if expiry <= today + timedelta(days=30):
        return "d0_30"
    return "d31_60" if expiry <= today + timedelta(days=60) else "later"


def sku_detail(conn: Connection, sku: str, today: date, forecast: ForecastMeans | None, with_cost: bool) -> dict[str, Any]:
    rows = conn.execute(select(variants.c.external_id, variants.c.sku, variants.c.name).where(variants.c.sku == sku).order_by(variants.c.external_id)).all()
    if len(rows) != 1:                       # none, or a SKU shared by two variants: never guess which product is meant
        raise SkuNotFound()
    vid, name = rows[0].external_id, rows[0].name
    states: list[str] = []

    on_hand = _on_hand(conn, today, None).get(vid)
    if on_hand is not None and on_hand < 0:
        states.append("negative_stock")
    per, _without = coverage_by_variant(conn, today, Filters(), {vid}, forecast)
    cover = per.get(vid)

    sold = conn.execute(select(func.coalesce(func.sum(demand_observations.c.demand_qty), 0)).where(
        demand_observations.c.variant_id == vid, ~demand_observations.c.censored,
        demand_observations.c.day > today - timedelta(days=DEMAND_DAYS), demand_observations.c.day <= today)).scalar_one()
    ever = conn.execute(select(func.count()).select_from(demand_observations).where(demand_observations.c.variant_id == vid)).scalar_one()
    if not ever:
        states.append("no_demand_history")

    mean = None
    if forecast is not None:
        try:
            mean = forecast.daily_means().get(vid)
        except Exception:
            mean = None

    by_lot, by_variant = _costs(conn)
    lots = conn.execute(select(stock_lots).where(stock_lots.c.variant_id == vid, stock_lots.c.quantity > 0).order_by(stock_lots.c.batch_number)).all()
    value, estimated, unvalued = Decimal(0), False, 0
    supplier = by_variant.get(vid)
    for lot in lots:
        found = by_lot.get((vid, lot.batch_number or ""))
        if found is None and supplier is not None:
            found, estimated = supplier, True
        if found is None:
            unvalued += 1
        else:
            value += found[0] * lot.quantity
    if estimated:
        states.append("cost_estimated")
    if unvalued or supplier is None:
        states.append("no_cost")

    out: dict[str, Any] = {
        "sku": sku, "name": name,
        "stock": {"on_hand": on_hand},
        "coverage": None if cover is None else {"days": str(cover[0].quantize(Decimal("0.01"))), "basis": cover[1]},
        "demand": {"units": int(sold), "days": DEMAND_DAYS},
        "forecast": None if mean is None else {"daily_mean": str(Decimal(str(mean)).quantize(Decimal("0.01"))), "days": FORECAST_DAYS},
        "supplier": None if supplier is None else {"id": supplier[1]},
        "expiry_lots": [{"batch": lot.batch_number or "", "quantity": lot.quantity, "expiry_date": lot.expiry_date.isoformat() if lot.expiry_date else None,
                         "band": _band(lot.expiry_date, today)} for lot in lots],
        "states": states,
    }
    if with_cost:
        out["cost"] = {"value": None if supplier is None else str(value.quantize(Decimal("0.01"))), "estimated": estimated,
                       "unit_cost": None if supplier is None else str(supplier[0].quantize(Decimal("0.01")))}
    return out
