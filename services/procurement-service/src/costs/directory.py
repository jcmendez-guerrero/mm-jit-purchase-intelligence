"""Product reference data held by procurement: variant -> product and the buyer-maintained VAT rate."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from db.tables import product_refs
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection


LOCAL_ID_FLOOR = 9_000_000          # ids assigned by the local export loader (research R1); they never exist in the ERP


def is_local_id(value: int | None) -> bool:
    return value is not None and int(value) >= LOCAL_ID_FLOOR


@dataclass(frozen=True)
class ProductRef:
    variant_id: int
    product_id: int
    vat_rate: Decimal | None


class SqlProductDirectory:
    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def by_variant(self, variant_id: int) -> ProductRef | None:
        r = self.conn.execute(select(product_refs).where(product_refs.c.variant_id == variant_id)).first()
        return ProductRef(r.variant_id, r.product_id, None if r.vat_rate is None else Decimal(str(r.vat_rate))) if r else None

    def erp_ids_for_sku(self, sku: str) -> tuple[int, int] | None:
        """(product_id, variant_id) the ERP knows for this SKU, or None when only a locally assigned id exists (the write stays pending)."""
        r = self.conn.execute(select(product_refs).where(func.lower(product_refs.c.sku) == sku.strip().lower()).order_by(product_refs.c.variant_id).limit(1)).first()
        if r is None or is_local_id(r.product_id) or is_local_id(r.variant_id):
            return None
        return int(r.product_id), int(r.variant_id)

    def vat_for_product(self, product_id: int) -> Decimal | None:
        r = self.conn.execute(select(product_refs.c.vat_rate).where(product_refs.c.product_id == product_id, product_refs.c.vat_rate.is_not(None)).limit(1)).first()
        return None if r is None else Decimal(str(r.vat_rate))

    def set_vat(self, product_id: int, vat_rate: Decimal | None) -> int:
        res = self.conn.execute(update(product_refs).where(product_refs.c.product_id == product_id).values(
            vat_rate=vat_rate, vat_source="buyer" if vat_rate is not None else None))
        return int(res.rowcount)
