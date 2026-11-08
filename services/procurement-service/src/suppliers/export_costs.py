"""T096 (FR-037, R16): the inventory export's cost and selling price per SKU, kept as a reference.

It is refreshed on every load, is the default cost when a product is linked to a supplier (source ``inventory_export``), and is
never a supplier cost and never written to the ERP. Money is exact decimals.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from db.tables import export_costs
from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection


def _key(sku: str) -> str:
    return sku.strip()


def upsert_export_costs(conn: Connection, rows: Iterable[dict[str, Any]], run_id: str | None, now: datetime) -> int:
    n = 0
    for r in rows:
        sku = _key(r["sku"])
        values = {"export_cost": r.get("export_cost"), "pvp_gross": r.get("pvp_gross"), "tax_rate": r.get("tax_rate"),
                  "tax_included": bool(r.get("tax_included", False)), "currency": r.get("currency") or "EUR", "loaded_at": now, "load_run_id": run_id}
        existing = conn.execute(select(export_costs.c.sku).where(func.lower(export_costs.c.sku) == sku.lower())).scalar()
        if existing is None:
            conn.execute(insert(export_costs).values(sku=sku, **values))
        else:
            conn.execute(update(export_costs).where(export_costs.c.sku == existing).values(**values))
        n += 1
    return n


def get_export_cost(conn: Connection, sku: str) -> dict[str, Any] | None:
    row = conn.execute(select(export_costs).where(func.lower(export_costs.c.sku) == _key(sku).lower())).first()
    return None if row is None else dict(row._mapping)
