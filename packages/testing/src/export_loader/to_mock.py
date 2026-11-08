"""T031: parsed exports → the Siweb mock's ``Dataset``, so the unchanged connector → inventory → forecast → procurement
pipeline runs on export data (research R2).

Products are keyed by SKU for people; the integer ids here are SKU-derived surrogates from the reserved range and never
leave the platform (FR-003, FR-040). Movement ids are derived from the movement's own time and content so reloading the same
or a longer export never renumbers old rows. Notes become a fixed placeholder, never the text.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from generator import Dataset, GenerationConfig

from .parse_inventory import InventoryItem, InventoryParse
from .parse_movements import Movement, MovementParse
from .sku_map import SkuMap

EPOCH = datetime(2020, 1, 1)  # noqa: DTZ001 - naive local time on purpose, like the ERP API
NOTE_PLACEHOLDER = "nota"
TRAILING_DIGITS = re.compile(r"(\d+)\s*$")
PURCHASE_NUMBER = re.compile(r"#\s*(\d+)")


def _content_hash(m: Movement, occurrence: int) -> str:
    raw = "|".join([m.raw_date, m.sku, m.reason, str(m.quantity), m.batch or "", m.warehouse or "", m.reference or "", str(occurrence)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _movement_ids(movements: list[Movement]) -> list[int]:
    """Ascending by time, stable for the same content: minutes since 2020 x 1000 + rank within the minute (by content hash)."""
    seen: dict[tuple, int] = {}
    keyed: list[tuple[int, str, int]] = []
    for idx, m in enumerate(movements):
        sig = (m.raw_date, m.sku, m.reason, m.quantity, m.batch, m.warehouse, m.reference)
        occ = seen.get(sig, 0)
        seen[sig] = occ + 1
        minute = int((m.when - EPOCH).total_seconds() // 60)
        keyed.append((minute, _content_hash(m, occ), idx))
    ids = [0] * len(movements)
    by_minute: dict[int, list[tuple[str, int]]] = {}
    for minute, h, idx in keyed:
        by_minute.setdefault(minute, []).append((h, idx))
    for minute, group in by_minute.items():
        group.sort()
        if len(group) >= 1000:
            raise ValueError("too many movements in the same minute")
        for slot, (_, idx) in enumerate(group):
            ids[idx] = minute * 1000 + slot
    return ids


def _reference(m: Movement) -> tuple[str | None, int | None, str | None]:
    if not m.reference:
        return None, None, None
    if m.reason == "sale_shipment":
        digits = TRAILING_DIGITS.search(m.reference)
        return "ticket", int(digits.group(1)) if digits else None, m.reference
    if m.reason == "purchase_receipt":
        digits = PURCHASE_NUMBER.search(m.reference) or TRAILING_DIGITS.search(m.reference)
        return "purchase", int(digits.group(1)) if digits else None, m.reference
    return None, None, m.reference


def _vat(item: InventoryItem) -> int | None:
    r = item.tax_rate
    return int(r) if r is not None and r == r.to_integral_value() else None


def build_dataset(inventory: InventoryParse, movements: MovementParse | None, sku_map: SkuMap) -> Dataset:
    moves = sorted(movements.movements, key=lambda m: (m.when, m.row)) if movements else []
    names: dict[str, str] = {}
    for m in moves:
        if m.warehouse:
            names.setdefault(" ".join(m.warehouse.split()).casefold(), m.warehouse)
    warehouses = [{"id": sku_map.warehouse_id(n), "name": names[k], "active": True} for k, n in sorted(names.items(), key=lambda kv: kv[1].casefold())]
    warehouses.sort(key=lambda w: w["id"])

    products: list[dict[str, Any]] = []
    variants: list[dict[str, Any]] = []
    suppliers: dict[int, list[dict[str, Any]]] = {}
    ids: dict[str, int] = {}
    for key, item in inventory.items.items():
        ident = sku_map.get_or_assign(item.sku)
        ids[key] = ident
        service = item.kind == "service"
        products.append({"id": ident, "name": item.name, "status": "active" if item.status == "active" else "inactive", "vat_rate": _vat(item),
                         "is_service": service})
        variants.append({"id": ident, "product_id": ident, "sku": item.sku, "name": item.name, "pack_size": 1, "uom": item.uom,
                         "reorder_point": item.reorder_point, "price_cents": int(item.pvp_gross * 100), "category": item.category,
                         "is_service": service})
        suppliers[ident] = []

    expiry: dict[tuple[str, str], str] = {}
    for m in moves:
        if m.batch and m.expiry_iso:
            expiry[(m.sku, m.batch)] = m.expiry_iso
    lots: list[dict[str, Any]] = []
    for key, item in inventory.items.items():
        if item.kind != "physical" or item.total <= 0:
            continue
        batched = 0
        for batch, qty in item.lots:
            if qty > 0:
                batched += qty
                lots.append({"variant_id": ids[key], "warehouse_id": None, "batch_number": batch, "expiry_date": expiry.get((key, batch)), "quantity": qty})
        if item.total - batched > 0:
            lots.append({"variant_id": ids[key], "warehouse_id": None, "batch_number": None, "expiry_date": None, "quantity": item.total - batched})

    movement_ids = _movement_ids(moves)
    out_moves: list[dict[str, Any]] = []
    for m, mid in sorted(zip(moves, movement_ids, strict=True), key=lambda p: p[1]):
        ref_type, ref_id, ref_no = _reference(m)
        ident = ids[m.sku]
        out_moves.append({
            "id": mid, "created_at": m.when.isoformat(timespec="seconds"), "variant_id": ident, "sku": inventory.items[m.sku].sku, "product_id": ident,
            "warehouse_id": sku_map.warehouse_id(m.warehouse) if m.warehouse else None, "location_id": None, "quantity": m.quantity,
            "movement_type": "in" if m.quantity > 0 else "out", "reason": m.reason, "reference_type": ref_type, "reference_id": ref_id,
            "reference_number": ref_no, "batch_number": m.batch, "expiry_date": m.expiry_iso or (m.expiry_raw or None), "unit_cost_cents": None,
            "notes": NOTE_PLACEHOLDER if m.has_note else "",
        })
    sku_map.save()
    return Dataset(GenerationConfig(), warehouses, products, variants, suppliers, lots, out_moves)


def dataset_to_json(ds: Dataset) -> dict[str, Any]:
    return {"warehouses": ds.warehouses, "products": ds.products, "variants": ds.variants,
            "suppliers": {str(k): v for k, v in ds.suppliers.items()}, "lots": ds.lots, "movements": ds.movements}


def dataset_from_json(body: dict[str, Any]) -> Dataset:
    return Dataset(GenerationConfig(), body["warehouses"], body["products"], body["variants"],
                   {int(k): v for k, v in body["suppliers"].items()}, body["lots"], body["movements"])
