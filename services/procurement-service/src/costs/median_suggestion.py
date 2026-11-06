"""T057: the median lot cost, the only value a supplier-cost update can carry (FR-040/042).

Eligible lots are those with stock remaining (looked up from inventory when the request is built) and a recorded acquisition
cost. A buyer-entered opening entry stands in when the ERP holds no cost and nothing else is eligible. Rounding is half-up to
cents because the ERP stores cents. No eligible lot means no request.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from db.tables import cost_write_requests, product_refs, supplier_costs
from sqlalchemy import select
from sqlalchemy.engine import Connection

from costs.lot_costs import OPENING_LOT, latest_by_lot
from costs.lot_lookup import LotsSource, fetch_lots
from costs.margin import evaluate
from costs.pvp import PvpSource, lowest_pvp
from costs.recargo import Q4
from costs.rules import load_rules
from costs.store import NewCost, add_version, current
from costs.writes import WriteRequestResult, request_write

CENT = Decimal("0.01")


@dataclass(frozen=True)
class LotUse:
    variant_id: int
    lot: str
    quantity: int
    unit_cost: Decimal


def median_cost(costs: list[Decimal]) -> Decimal | None:
    """Median of the lot costs (one value per lot), half-up to cents; None when empty."""
    if not costs:
        return None
    s = sorted(costs)
    n = len(s)
    mid = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    return Decimal(mid).quantize(CENT, rounding=ROUND_HALF_UP)


def eligible_lots(conn: Connection, source: LotsSource, product_id: int, supplier_id: str) -> list[LotUse]:
    variants = [r.variant_id for r in conn.execute(select(product_refs.c.variant_id).where(product_refs.c.product_id == product_id)).all()]
    if not variants:
        return []
    stock = fetch_lots(source, variants)
    out: list[LotUse] = []
    for v in variants:
        entries = latest_by_lot(conn, v, supplier_id)
        for item in stock:
            if item["variant_id"] != v or not item.get("lot") or int(item["quantity"]) <= 0:
                continue
            e = entries.get(item["lot"])
            if e is not None:
                out.append(LotUse(v, item["lot"], int(item["quantity"]), Decimal(str(e.unit_cost))))
    if out:
        return out
    for v in variants:                                            # opening entry: no eligible lot at all
        e = latest_by_lot(conn, v, supplier_id).get(OPENING_LOT)
        if e is not None:
            out.append(LotUse(v, OPENING_LOT, 0, Decimal(str(e.unit_cost))))
    return out


def request_median_write(conn: Connection, source: LotsSource, product_id: int, supplier_id: str, trigger: str, actor: str,
                         now: datetime | None = None, pvp_source: PvpSource | None = None) -> WriteRequestResult:
    """Creates (for review, never sent) the request carrying the median, or reports ``not_applicable`` when no lot qualifies."""
    now = now or datetime.now(UTC)
    lots = eligible_lots(conn, source, product_id, supplier_id)
    median = median_cost([u.unit_cost for u in lots])
    if median is None:
        return WriteRequestResult(None, "not_applicable", ["no_lots_in_stock"])
    cur = current(conn, product_id, supplier_id, None)
    if cur is None or Decimal(str(cur.cost_with_recargo)).quantize(CENT, rounding=ROUND_HALF_UP) != median:
        cur = add_version(conn, NewCost(product_id=product_id, supplier_id=supplier_id, cost_with_recargo=median.quantize(Q4), source="manual", actor=actor,
                                        pack_size=cur.pack_size if cur else None, lead_time_days=cur.lead_time_days if cur else None,
                                        min_order_qty=cur.min_order_qty if cur else None), load_rules(conn), now)
    refs: list[dict[str, Any]] = [{"variant_id": u.variant_id, "lot": u.lot, "quantity": u.quantity, "unit_cost": str(u.unit_cost)} for u in lots]
    margin = None
    if pvp_source is not None:
        previous = conn.execute(select(supplier_costs.c.cost_with_recargo).where(
            supplier_costs.c.product_id == product_id, supplier_costs.c.supplier_id == supplier_id, supplier_costs.c.variant_id.is_(None),
            supplier_costs.c.source == "siweb_product_supplier").order_by(supplier_costs.c.version.desc()).limit(1)).scalar()
        margin = evaluate(median, None if previous is None else Decimal(str(previous)),
                          lowest_pvp(pvp_source, sorted({u.variant_id for u in lots}) or [r.variant_id for r in conn.execute(
                              select(product_refs.c.variant_id).where(product_refs.c.product_id == product_id)).all()]))
    res = request_write(conn, cur.id, trigger, actor, now, median_lot_refs=refs, median_cost=median, margin=margin)
    return res


def lots_view(conn: Connection, request_id: str) -> dict[str, Any] | None:
    r = conn.execute(select(cost_write_requests).where(cost_write_requests.c.id == request_id)).first()
    if r is None:
        return None
    return {"median_cost": None if r.median_cost is None else str(Decimal(str(r.median_cost)).quantize(CENT)), "lots": r.median_lot_refs or []}



