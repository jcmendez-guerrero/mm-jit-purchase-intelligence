"""Normalise raw Siweb records into the stored shape.

Rules (AGENTS.md 5-7): money is Decimal; timestamps are stored as UTC plus the original string;
products are keyed by Siweb ``variant_id``; ``supplier_cif`` and free-text ``notes`` are discarded
(only ``has_note`` survives). ``strip_sensitive`` is also applied before raw payloads are written.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from mmi_common.money import Money
from mmi_common.time import parse_siweb_timestamp

UNASSIGNED_WAREHOUSE_ID = 0
DROPPED_FIELDS = frozenset({"supplier_cif", "notes"})


def strip_sensitive(obj: Any) -> Any:
    """Recursively remove dropped fields; ``notes`` becomes a ``has_note`` flag. Safe for raw payloads."""
    if isinstance(obj, list):
        return [strip_sensitive(x) for x in obj]
    if isinstance(obj, dict):
        out = {k: strip_sensitive(v) for k, v in obj.items() if k not in DROPPED_FIELDS}
        if "notes" in obj:
            out["has_note"] = bool((obj.get("notes") or "").strip()) if isinstance(obj.get("notes"), str) else bool(obj.get("notes"))
        return out
    return obj


@dataclass(frozen=True)
class NormalisedMovement:
    external_id: int
    variant_id: int
    product_id: int | None
    warehouse_id: int
    occurred_at: datetime  # UTC
    occurred_at_raw: str
    timestamp_ambiguous: bool
    quantity: int
    movement_type: str
    reason: str
    reference_type: str | None
    reference_id: int | None
    reference_number: str | None
    batch_number: str | None
    expiry_date: date | None
    unit_cost: Decimal | None
    has_note: bool


def parse_expiry(value: Any) -> date | None:
    """None for no expiry; raises ValueError("malformed expiry ...") for bad values (quarantined by the quality gates)."""
    if value in (None, ""):
        return None
    try:
        if not isinstance(value, str) or len(value) < 10 or value[4] != "-":
            raise ValueError
        return date.fromisoformat(value[:10])
    except ValueError:
        raise ValueError("malformed expiry date") from None


def normalise_movement(raw: dict[str, Any]) -> NormalisedMovement:
    ts = parse_siweb_timestamp(raw["created_at"])
    cost = raw.get("unit_cost_cents")
    warehouse = raw.get("warehouse_id")
    return NormalisedMovement(
        external_id=int(raw["id"]),
        variant_id=int(raw["variant_id"]),
        product_id=int(raw["product_id"]) if raw.get("product_id") is not None else None,
        warehouse_id=int(warehouse) if warehouse is not None else UNASSIGNED_WAREHOUSE_ID,
        occurred_at=ts.utc,
        occurred_at_raw=raw["created_at"],
        timestamp_ambiguous=ts.ambiguous,
        quantity=int(raw["quantity"]),
        movement_type=str(raw.get("movement_type") or ""),
        reason=str(raw["reason"]),
        reference_type=raw.get("reference_type"),
        reference_id=int(raw["reference_id"]) if raw.get("reference_id") is not None else None,
        reference_number=raw.get("reference_number"),
        batch_number=raw.get("batch_number"),
        expiry_date=parse_expiry(raw.get("expiry_date")),
        unit_cost=Money.from_cents(str(cost)).amount if cost not in (None, "") else None,
        has_note=bool((raw.get("notes") or "").strip()) if isinstance(raw.get("notes"), str) else False,
    )


def normalise_supplier_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Supplier cost row with ``supplier_cif`` discarded and the cost in EUR as Decimal."""
    cost = raw.get("purchase_cost_cents")
    return {
        "external_id": int(raw["id"]),
        "product_id": int(raw["product_id"]),
        "contact_id": int(raw["contact_id"]),
        "supplier_name": raw.get("supplier_name"),
        "purchase_cost": Money.from_cents(str(cost), raw.get("currency") or "EUR").amount if cost is not None else None,
        "currency": raw.get("currency") or "EUR",
        "lead_time_days": raw.get("lead_time_days"),
        "min_order_qty": raw.get("min_order_qty"),
        "is_preferred": bool(raw.get("is_preferred")),
    }
