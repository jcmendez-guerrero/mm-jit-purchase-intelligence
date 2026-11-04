"""Apply a siweb.sync.completed.v1 payload to the inventory projections. Idempotent: re-applying changes nothing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from db.tables import (
    ALL_WAREHOUSES,
    UNASSIGNED_WAREHOUSE,
    products,
    stock_movements,
    stock_snapshots,
    variants,
    warehouses,
)
from mmi_common.money import Money
from mmi_common.time import parse_siweb_timestamp
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

TOMBSTONE_AFTER_DEFAULT = 3
CHUNK = 500


def apply_payload(conn: Connection, doc: dict[str, Any], snapshot_date: date, tombstone_after: int = TOMBSTONE_AFTER_DEFAULT) -> int:
    kind = doc["kind"]
    records = doc.get("records", [])
    if kind == "warehouses":
        return _warehouses(conn, records)
    if kind == "products":
        return _products(conn, records, bool(doc.get("reconciled")), tombstone_after)
    if kind == "variants":
        return _variants(conn, records, snapshot_date)
    if kind == "movements":
        return _movements(conn, records, {int(k): ",".join(v) for k, v in doc.get("quarantined", {}).items()})
    raise ValueError(f"unknown sync kind: {kind}")


def _ensure_unassigned(conn: Connection) -> None:
    if conn.execute(select(warehouses.c.external_id).where(warehouses.c.external_id == UNASSIGNED_WAREHOUSE)).first() is None:
        conn.execute(insert(warehouses).values(external_id=UNASSIGNED_WAREHOUSE, name="Sin asignar", is_unassigned=True))


def _upsert(conn: Connection, table: Any, key: str, row: dict[str, Any]) -> None:
    if conn.execute(select(table.c[key]).where(table.c[key] == row[key])).first() is None:
        conn.execute(insert(table).values(**row))
    else:
        conn.execute(update(table).where(table.c[key] == row[key]).values(**{k: v for k, v in row.items() if k != key}))


def _warehouses(conn: Connection, records: list[dict[str, Any]]) -> int:
    _ensure_unassigned(conn)
    for r in records:
        _upsert(conn, warehouses, "external_id", {"external_id": int(r["id"]), "name": str(r.get("name") or r["id"]), "is_unassigned": False})
    return len(records)


def _vat(value: Any) -> Decimal | None:
    return None if value in (None, "") else Decimal(str(value))


def _products(conn: Connection, records: list[dict[str, Any]], reconciled: bool, tombstone_after: int) -> int:
    present = set()
    for r in records:
        pid = int(r["id"])
        present.add(pid)
        row = {"external_id": pid, "name": str(r.get("name") or pid), "status": "active", "missed_syncs": 0}
        vat = _vat(r.get("vat_rate"))
        existing = conn.execute(select(products.c.external_id).where(products.c.external_id == pid)).first()
        if existing is None:
            conn.execute(insert(products).values(**row, vat_rate=vat))
        else:  # reappearing reactivates; the buyer's VAT/critical settings are never overwritten by a missing value
            values = {**{k: v for k, v in row.items() if k != "external_id"}, **({"vat_rate": vat} if vat is not None else {})}
            conn.execute(update(products).where(products.c.external_id == pid).values(**values))
    if reconciled:  # only a complete, reconciled list can prove a product is gone; a short list never tombstones
        for row in conn.execute(select(products.c.external_id, products.c.missed_syncs).where(products.c.status == "active")).all():
            if row.external_id in present:
                continue
            missed = row.missed_syncs + 1
            conn.execute(update(products).where(products.c.external_id == row.external_id).values(
                missed_syncs=missed, status="discontinued" if missed >= tombstone_after else "active"))
    return len(records)


def _variants(conn: Connection, records: list[dict[str, Any]], snapshot_date: date) -> int:
    for r in records:
        vid = int(r["id"])
        pid = int(r["product_id"]) if r.get("product_id") is not None else None
        if pid is not None and conn.execute(select(products.c.external_id).where(products.c.external_id == pid)).first() is None:
            conn.execute(insert(products).values(external_id=pid, name=str(r.get("product_name") or pid), status="active", missed_syncs=0))
        _upsert(conn, variants, "external_id", {
            "external_id": vid, "product_id": pid, "sku": r.get("sku"), "name": r.get("name"),
            "pack_size": r.get("pack_size"), "uom": r.get("uom"), "reorder_point": r.get("reorder_point")})
        on_hand = int(r.get("total_on_hand", r.get("stock_total", 0)) or 0)
        reserved = int(r.get("total_reserved", 0) or 0)
        available = int(r["total_available"]) if r.get("total_available") is not None else on_hand - reserved
        snap = {"variant_id": vid, "warehouse_id": ALL_WAREHOUSES, "snapshot_date": snapshot_date,
                "on_hand": on_hand, "available": available, "reserved": reserved}
        where = (stock_snapshots.c.variant_id == vid) & (stock_snapshots.c.warehouse_id == ALL_WAREHOUSES) & (stock_snapshots.c.snapshot_date == snapshot_date)
        if conn.execute(select(stock_snapshots.c.variant_id).where(where)).first() is None:
            conn.execute(insert(stock_snapshots).values(**snap))
        else:
            conn.execute(update(stock_snapshots).where(where).values(on_hand=on_hand, available=available, reserved=reserved))
    return len(records)


def _safe_expiry(value: Any) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if isinstance(value, str) and len(value) >= 10 and value[4] == "-" else None
    except ValueError:
        return None


def _movement_row(r: dict[str, Any], quarantined: bool, codes: str | None = None) -> dict[str, Any]:
    cost = r.get("unit_cost_cents")
    try:
        created = parse_siweb_timestamp(r["created_at"]).utc
    except (KeyError, ValueError):
        created, quarantined = None, True
    has_note = bool(r.get("has_note")) or bool((r.get("notes") or "").strip() if isinstance(r.get("notes"), str) else False)
    return {  # the note text itself is never copied anywhere
        "external_id": int(r["id"]), "created_at_utc": created, "created_at_raw": str(r.get("created_at")),
        "variant_id": int(r["variant_id"]),
        "warehouse_id": int(r["warehouse_id"]) if r.get("warehouse_id") is not None else UNASSIGNED_WAREHOUSE,
        "quantity": int(r["quantity"]), "movement_type": r.get("movement_type"), "reason": str(r["reason"]),
        "reference_type": r.get("reference_type"),
        "reference_id": int(r["reference_id"]) if r.get("reference_id") is not None else None,
        "reference_number": r.get("reference_number"), "batch_number": r.get("batch_number"),
        "expiry_date": _safe_expiry(r.get("expiry_date")),
        "unit_cost": Money.from_cents(str(cost)).amount if cost not in (None, "") else None,
        "has_note": has_note, "quarantined": quarantined, "quarantine_codes": codes,
    }


def _movements(conn: Connection, records: list[dict[str, Any]], quarantined: dict[int, str]) -> int:
    _ensure_unassigned(conn)
    stored = 0
    for start in range(0, len(records), CHUNK):
        chunk = records[start:start + CHUNK]
        ids = [int(r["id"]) for r in chunk]
        known = set(conn.execute(select(stock_movements.c.external_id).where(stock_movements.c.external_id.in_(ids))).scalars())
        new_rows = []
        for r in chunk:
            if int(r["id"]) in known:
                continue
            rid = int(r["id"])
            new_rows.append(_movement_row(r, rid in quarantined, quarantined.get(rid)))
        if new_rows:
            conn.execute(insert(stock_movements), new_rows)
            stored += len(new_rows)
    return stored
