"""MMI-7 T073: the product lookups a seed file is checked against, built once from the inventory series (used by the API route and by the background worker).

A SKU maps to a *set* of products: the ERP does not guarantee that SKUs are unique, and two products with the same SKU must be reported as ambiguous
(``import_ambiguous_sku``), never resolved to whichever comes last.
"""

from __future__ import annotations

from typing import Any


def lookups_from_series(series: list[dict[str, Any]]) -> tuple[set[int], dict[str, set[int]]]:
    """(known variant ids, SKU -> variants). Items without a SKU are known but cannot be matched by SKU."""
    known: set[int] = set()
    skus: dict[str, set[int]] = {}
    for item in series:
        variant = int(item["variant_id"])
        known.add(variant)
        if item.get("sku"):
            skus.setdefault(str(item["sku"]), set()).add(variant)
    return known, skus
