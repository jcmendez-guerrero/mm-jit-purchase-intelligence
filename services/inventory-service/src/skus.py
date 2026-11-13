"""People use SKUs; the ERP variant id stays inside the platform (project rule 5). A SKU that matches no variant, or more than one (also by case or spacing), is refused."""

from __future__ import annotations

from db.tables import variants
from sqlalchemy import func, select
from sqlalchemy.engine import Connection


class SkuError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def resolve_sku(conn: Connection, sku: str) -> tuple[int, int | None, str]:
    """Returns (variant id, product id, SKU as stored)."""
    key = (sku or "").strip().lower()
    if not key:
        raise SkuError("sku_unknown")
    rows = conn.execute(select(variants.c.external_id, variants.c.product_id, variants.c.sku).where(func.lower(func.trim(variants.c.sku)) == key)).all()
    if not rows:
        raise SkuError("sku_unknown")
    if len(rows) > 1:
        raise SkuError("sku_ambiguous")
    r = rows[0]
    return int(r.external_id), None if r.product_id is None else int(r.product_id), str(r.sku).strip()
