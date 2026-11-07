"""T120 / T126 / T128: dashboard figures computed from stock, lots, the lot-cost projection, demand and (when available) the forecast.

* Inventory value (FR-041) = quantity per lot x that lot's acquisition cost. A lot with no recorded cost uses the latest known cost of the
  same variant, labelled as an estimate and counted; with no cost at all it is left out of the value and counted as unvalued. It is never
  valued at zero silently and never at the selling price (PVP).
* Coverage days = stock on hand / average daily demand: the forecast mean over the next 28 days when the variant is forecast-eligible, otherwise
  the actual average over the last 90 days; the basis is returned per variant count. No demand -> no number ("sin demanda").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from db.tables import (
    ALL_WAREHOUSES,
    agg_abc_xyz,
    agg_daily_kpis,
    demand_observations,
    lot_cost_projection,
    product_segments,
    products,
    stock_lots,
    stock_snapshots,
    variants,
    warehouses,
)
from risk.daily import evaluate_risks
from sqlalchemy import delete, func, insert, select
from sqlalchemy.engine import Connection

ACTUAL_DAYS = 90
EXPIRY_DAYS = 60
CATEGORIES = ("A", "B", "C", "critical")
ZERO = Decimal(0)


class ForecastMeans(Protocol):
    def daily_means(self) -> dict[int, float]:
        """variant_id -> forecast mean units per day over the next 28 days, for forecast-eligible variants only."""
        ...


@dataclass
class Filters:
    warehouse_id: int | None = None
    category: str | None = None          # A / B / C / critical
    family: str | None = None            # ERP product family name, exactly as synchronised


@dataclass
class Summary:
    day: date
    inventory_value: Decimal = ZERO
    valued_with_estimate: int = 0
    unvalued_lots: int = 0
    expiring_value: Decimal = ZERO
    stockout_risk: int = 0
    expiry_risk: int = 0
    coverage_days_avg: Decimal | None = None
    variants_without_demand: int = 0
    basis: dict[str, int] = field(default_factory=lambda: {"forecast": 0, "actual_90d": 0})
    variant_count: int = 0

    def as_json(self) -> dict[str, Any]:
        q = lambda v: None if v is None else str(v.quantize(Decimal("0.01")))  # noqa: E731
        return {"day": self.day.isoformat(), "inventory_value": q(self.inventory_value), "valued_with_estimate": self.valued_with_estimate, "unvalued_lots": self.unvalued_lots,
                "value_basis": "lot_acquisition_cost", "expiring_value": q(self.expiring_value), "stockout_risk": self.stockout_risk, "expiry_risk": self.expiry_risk,
                "coverage_days_avg": q(self.coverage_days_avg), "variants_without_demand": self.variants_without_demand, "coverage_basis": dict(self.basis),
                "variant_count": self.variant_count}


def variant_scope(conn: Connection, f: Filters) -> set[int]:
    ids = {r.external_id for r in conn.execute(select(variants.c.external_id)).all()}
    if f.family is not None:
        in_family = {r.external_id for r in conn.execute(select(variants.c.external_id).join(products, products.c.external_id == variants.c.product_id)
                                                         .where(products.c.family == f.family)).all()}
        ids &= in_family
    if f.category is None:
        return ids
    if f.category == "critical":
        crit = {r.external_id for r in conn.execute(select(products.c.external_id).where(products.c.clinical_critical)).all()}
        return {r.external_id for r in conn.execute(select(variants.c.external_id, variants.c.product_id)).all() if r.product_id in crit}
    return {r.variant_id for r in conn.execute(select(product_segments.c.variant_id).where(product_segments.c.abc == f.category)).all()} & ids


def _costs(conn: Connection) -> tuple[dict[tuple[int, str], Decimal], dict[int, Decimal]]:
    """(variant, lot) -> latest cost, and variant -> latest cost of any lot (the labelled fallback)."""
    by_lot: dict[tuple[int, str], tuple[datetime, Decimal]] = {}
    by_variant: dict[int, tuple[datetime, Decimal]] = {}
    for r in conn.execute(select(lot_cost_projection)).all():
        at, cost = r.updated_at, Decimal(str(r.unit_cost))
        if (r.variant_id, r.lot) not in by_lot or by_lot[(r.variant_id, r.lot)][0] <= at:
            by_lot[(r.variant_id, r.lot)] = (at, cost)
        if r.variant_id not in by_variant or by_variant[r.variant_id][0] <= at:
            by_variant[r.variant_id] = (at, cost)
    return {k: v[1] for k, v in by_lot.items()}, {k: v[1] for k, v in by_variant.items()}


def compute_summary(conn: Connection, today: date, f: Filters | None = None, forecast: ForecastMeans | None = None) -> Summary:
    f = f or Filters()
    scope = variant_scope(conn, f)
    out = Summary(today, variant_count=len(scope))
    by_lot, by_variant = _costs(conn)
    horizon = today + timedelta(days=EXPIRY_DAYS)
    q = select(stock_lots).where(stock_lots.c.quantity > 0)
    if f.warehouse_id is not None:
        q = q.where(stock_lots.c.warehouse_id == f.warehouse_id)
    for lot in conn.execute(q).all():
        if lot.variant_id not in scope:
            continue
        cost = by_lot.get((lot.variant_id, lot.batch_number or ""))
        estimated = False
        if cost is None:
            cost, estimated = by_variant.get(lot.variant_id), True
        if cost is None:
            out.unvalued_lots += 1
            continue
        value = cost * lot.quantity
        out.inventory_value += value
        out.valued_with_estimate += 1 if estimated else 0
        if lot.expiry_date is not None and lot.expiry_date <= horizon:
            out.expiring_value += value
    risks = [r for r in evaluate_risks(conn, warehouse_id=f.warehouse_id, as_of=today, expiry_horizon_days=EXPIRY_DAYS) if r["variant_id"] in scope]
    out.stockout_risk = sum(1 for r in risks if r["risk_type"] == "stockout")
    out.expiry_risk = sum(1 for r in risks if r["risk_type"] == "expiry")
    _coverage(conn, today, f, scope, forecast, out)
    return out


def _on_hand(conn: Connection, today: date, warehouse_id: int | None) -> dict[int, int]:
    target = ALL_WAREHOUSES if warehouse_id is None else warehouse_id
    sub = (select(stock_snapshots.c.variant_id, func.max(stock_snapshots.c.snapshot_date).label("d")).where(stock_snapshots.c.warehouse_id == target, stock_snapshots.c.snapshot_date <= today)
           .group_by(stock_snapshots.c.variant_id).subquery())
    rows = conn.execute(select(stock_snapshots.c.variant_id, stock_snapshots.c.on_hand).join(sub, (stock_snapshots.c.variant_id == sub.c.variant_id) & (stock_snapshots.c.snapshot_date == sub.c.d))
                        .where(stock_snapshots.c.warehouse_id == target)).all()
    return {r.variant_id: r.on_hand for r in rows}


def _coverage(conn: Connection, today: date, f: Filters, scope: set[int], forecast: ForecastMeans | None, out: Summary) -> None:
    means = forecast.daily_means() if forecast is not None else {}
    since = today - timedelta(days=ACTUAL_DAYS)
    dq = select(demand_observations.c.variant_id, func.sum(demand_observations.c.demand_qty).label("q")).where(demand_observations.c.day > since, demand_observations.c.day <= today)
    if f.warehouse_id is not None:
        dq = dq.where(demand_observations.c.warehouse_id == f.warehouse_id)
    actual = {r.variant_id: Decimal(str(r.q)) / ACTUAL_DAYS for r in conn.execute(dq.group_by(demand_observations.c.variant_id)).all()}
    days: list[Decimal] = []
    for vid, on_hand in _on_hand(conn, today, f.warehouse_id).items():
        if vid not in scope:
            continue
        rate, basis = (Decimal(str(means[vid])), "forecast") if vid in means else (actual.get(vid, ZERO), "actual_90d")
        if rate <= 0:
            out.variants_without_demand += 1
            continue
        out.basis[basis] += 1
        days.append(Decimal(max(on_hand, 0)) / rate)
    out.coverage_days_avg = sum(days, ZERO) / len(days) if days else None


def refresh_aggregates(conn: Connection, today: date | None = None, forecast: ForecastMeans | None = None, now: datetime | None = None) -> int:
    """Stores today's figures for the company, each warehouse and each category (the worker runs this after each sync). Returns rows written."""
    today = today or datetime.now(UTC).date()
    now = now or datetime.now(UTC)
    conn.execute(delete(agg_daily_kpis).where(agg_daily_kpis.c.day == today))
    conn.execute(delete(agg_abc_xyz).where(agg_abc_xyz.c.day == today))
    wh = [None, *[r.external_id for r in conn.execute(select(warehouses.c.external_id).where(warehouses.c.is_unassigned.is_(False))).all()]]
    rows = []
    for w in wh:
        for cat in (None, *CATEGORIES):
            s = compute_summary(conn, today, Filters(w, cat), forecast)
            rows.append({"day": today, "warehouse_id": w, "category_id": cat, "supplier_id": None, "inventory_value": s.inventory_value, "valued_with_estimate_count": s.valued_with_estimate,
                         "coverage_days_avg": s.coverage_days_avg, "stockout_risk_count": s.stockout_risk, "expiring_value": s.expiring_value, "refreshed_at": now})
    conn.execute(insert(agg_daily_kpis), rows)
    dist = abc_xyz_distribution(conn)
    if dist:
        conn.execute(insert(agg_abc_xyz), [{"day": today, **d} for d in dist])
    return len(rows) + len(dist)


def abc_xyz_distribution(conn: Connection) -> list[dict[str, Any]]:
    out: dict[tuple[str, str], list[Any]] = {}
    for r in conn.execute(select(product_segments)).all():
        c = out.setdefault((r.abc, r.xyz), [0, ZERO])
        c[0] += 1
        c[1] += Decimal(str((r.metrics or {}).get("value", 0)))
    return [{"abc": a, "xyz": x, "variant_count": n, "value": v} for (a, x), (n, v) in sorted(out.items())]


def demand_trend(conn: Connection, today: date, days: int, f: Filters) -> list[dict[str, Any]]:
    scope = variant_scope(conn, f)
    since = today - timedelta(days=days)
    q = select(demand_observations.c.day, demand_observations.c.variant_id, demand_observations.c.demand_qty, demand_observations.c.censored).where(
        demand_observations.c.day > since, demand_observations.c.day <= today)
    if f.warehouse_id is not None:
        q = q.where(demand_observations.c.warehouse_id == f.warehouse_id)
    by_day: dict[date, list[int]] = {}
    for r in conn.execute(q).all():
        if r.variant_id in scope:
            c = by_day.setdefault(r.day, [0, 0])
            c[0] += r.demand_qty
            c[1] += 1 if r.censored else 0
    return [{"day": d.isoformat(), "actual": v[0], "censored_rows": v[1], "kind": "actual_erp"} for d, v in sorted(by_day.items())]


def filter_options(conn: Connection) -> dict[str, Any]:
    whs = [{"id": r.external_id, "name": r.name} for r in conn.execute(select(warehouses).where(warehouses.c.is_unassigned.is_(False)).order_by(warehouses.c.name)).all()]
    present = {r.abc for r in conn.execute(select(product_segments.c.abc).distinct()).all()}
    cats = [{"id": c, "kind": "demand_group"} for c in ("A", "B", "C") if c in present]
    if conn.execute(select(func.count()).select_from(products).where(products.c.clinical_critical)).scalar():
        cats.append({"id": "critical", "kind": "clinical_critical"})
    fams = [r.family for r in conn.execute(select(products.c.family).where(products.c.family.is_not(None)).distinct().order_by(products.c.family)).all()]
    return {"warehouses": whs, "categories": cats, "families": [{"id": f} for f in fams], "family_available": bool(fams)}
