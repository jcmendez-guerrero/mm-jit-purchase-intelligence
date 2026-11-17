"""People use SKUs (project rule 5, feature 014 FR-008a): rows that name a product by its internal id also carry the SKU, so the gateway can drop the id."""

from __future__ import annotations

from typing import Any

from db.tables import product_refs
from sqlalchemy import select
from sqlalchemy.engine import Connection


def _ids(value: Any, found: set[int]) -> None:
    if isinstance(value, dict):
        if isinstance(value.get("variant_id"), int) and not isinstance(value.get("variant_id"), bool):
            found.add(value["variant_id"])
        for v in value.values():
            _ids(v, found)
    elif isinstance(value, list):
        for v in value:
            _ids(v, found)


def _apply(value: Any, shown: dict[int, str | None]) -> Any:
    if isinstance(value, dict):
        out = {k: _apply(v, shown) for k, v in value.items()}
        vid = value.get("variant_id")
        if isinstance(vid, int) and not isinstance(vid, bool) and "sku" not in value:
            out["sku"] = shown.get(vid)
            if out["sku"] is None:
                out["sku_missing"] = True            # the gateway drops the id, so a product with no SKU is flagged for review, never shown as a blank row
        return out
    if isinstance(value, list):
        return [_apply(v, shown) for v in value]
    return value


def with_skus(conn: Connection, payload: Any) -> Any:
    """One query for all ids in the payload; an id with no SKU gets `None`."""
    found: set[int] = set()
    _ids(payload, found)
    if not found:
        return payload
    rows = conn.execute(select(product_refs.c.variant_id, product_refs.c.sku).where(product_refs.c.variant_id.in_(sorted(found)))).all()
    return _apply(payload, {int(r.variant_id): (None if r.sku is None else str(r.sku).strip()) for r in rows})
