"""T056: lot acquisition cost ledger (FR-040/041).

What a lot cost to acquire is held here because the ERP exposes only the selling price (PVP) in stock movements and one unit
cost per supplier. Entries are Recargo-inclusive, append-only and non-negative; a correction is a new entry for the same lot
(the latest wins, the history stays). The value never comes from an ERP movement price: the only sources are the confirmed
order cost at receipt matching, a buyer correction on arrival and a buyer-entered opening entry.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from audit.chain import append as audit
from db.tables import lot_acquisition_costs, product_refs
from mmi_common.time import get_correlation_id, set_correlation_id
from proposals.publisher import BlobWriter, lot_cost_changed
from sqlalchemy import insert, select
from sqlalchemy.engine import Connection, Row

from costs.recargo import Q4, UnknownVatError, gross_from_net, load_table

SOURCES = ("confirmed_order", "receipt_correction", "buyer_entry")
OPENING_LOT = "opening"          # buyer-entered cost for a pair whose ERP record has none


class LotCostError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def with_recargo(conn: Connection, variant_id: int, amount: Decimal, includes_recargo: bool) -> Decimal:
    """Converts a net entry with the product's VAT; refuses when the VAT is unknown (the same rule as supplier costs)."""
    if isinstance(amount, float):
        raise TypeError("floats are not allowed for money")
    if amount < 0:
        raise LotCostError("negative_cost")
    if includes_recargo:
        return amount.quantize(Q4)
    vat = conn.execute(select(product_refs.c.vat_rate).where(product_refs.c.variant_id == variant_id)).scalar()
    try:
        return gross_from_net(amount, load_table(conn).rate_for(None if vat is None else Decimal(str(vat))))
    except UnknownVatError as exc:
        raise LotCostError("vat_unknown") from exc


def record_lot_cost(conn: Connection, writer: BlobWriter, *, variant_id: int, supplier_id: str, lot: str, unit_cost: Decimal, source: str, actor: str,
                    quantity: int = 0, order_ref: str | None = None, received_at: datetime | None = None, now: datetime | None = None) -> Row[Any]:
    """``unit_cost`` is already Recargo-inclusive (use ``with_recargo`` for net entries)."""
    if source not in SOURCES:
        raise LotCostError("invalid_source")
    if not lot or not lot.strip() or len(lot) > 60:
        raise LotCostError("invalid_lot")
    if isinstance(unit_cost, float):
        raise TypeError("floats are not allowed for money")
    if unit_cost < 0:
        raise LotCostError("negative_cost")
    if quantity < 0:
        raise LotCostError("negative_quantity")
    now = now or datetime.now(UTC)
    rid = str(uuid.uuid4())
    conn.execute(insert(lot_acquisition_costs).values(
        id=rid, variant_id=variant_id, supplier_id=supplier_id, order_ref=order_ref, lot=lot.strip(), received_at=received_at or now, quantity=quantity,
        unit_cost=unit_cost.quantize(Q4), source=source, recorded_by=actor, recorded_at=now))
    audit(conn, actor, "lot_cost.recorded", "lot_cost", rid, after={"variant_id": variant_id, "supplier_id": supplier_id, "lot": lot.strip(), "source": source,
                                                                     "unit_cost": str(unit_cost.quantize(Q4))}, now=now)
    lot_cost_changed(conn, writer, variant_id, supplier_id, lot.strip(), rid, get_correlation_id() or set_correlation_id(), str(unit_cost.quantize(Q4)), source)
    return conn.execute(select(lot_acquisition_costs).where(lot_acquisition_costs.c.id == rid)).one()


def latest_by_lot(conn: Connection, variant_id: int, supplier_id: str) -> dict[str, Row[Any]]:
    """The current entry per lot: the most recent record; earlier ones stay as history."""
    rows = conn.execute(select(lot_acquisition_costs).where(
        lot_acquisition_costs.c.variant_id == variant_id, lot_acquisition_costs.c.supplier_id == supplier_id)
        .order_by(lot_acquisition_costs.c.recorded_at, lot_acquisition_costs.c.id)).all()
    return {r.lot: r for r in rows}


def history(conn: Connection, variant_id: int, supplier_id: str, lot: str) -> list[Row[Any]]:
    return list(conn.execute(select(lot_acquisition_costs).where(
        lot_acquisition_costs.c.variant_id == variant_id, lot_acquisition_costs.c.supplier_id == supplier_id, lot_acquisition_costs.c.lot == lot)
        .order_by(lot_acquisition_costs.c.recorded_at, lot_acquisition_costs.c.id)).all())
