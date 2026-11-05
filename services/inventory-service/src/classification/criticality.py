"""T064: clinical criticality is a manual, audited flag. It is never inferred from sales, names or notes."""

from __future__ import annotations

from datetime import datetime

from db.tables import criticality_changes, products
from mmi_common.time import utc_now
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection


class CriticalityError(Exception):
    code = "unknown_product"


def set_critical(conn: Connection, product_id: int, critical: bool, changed_by: str, now: datetime | None = None) -> bool:
    """Returns True when the value changed. Unknown products are refused rather than created."""
    row = conn.execute(select(products.c.clinical_critical).where(products.c.external_id == product_id)).first()
    if row is None:
        raise CriticalityError(f"unknown product {product_id}")
    if bool(row.clinical_critical) == critical:
        return False
    conn.execute(update(products).where(products.c.external_id == product_id).values(clinical_critical=critical))
    conn.execute(insert(criticality_changes).values(product_id=product_id, clinical_critical=critical, changed_by=changed_by, changed_at=now or utc_now()))
    return True


def critical_products(conn: Connection) -> set[int]:
    return set(conn.execute(select(products.c.external_id).where(products.c.clinical_critical)).scalars())
