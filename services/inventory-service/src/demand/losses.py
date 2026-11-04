"""T052: classify non-demand movements into separate flow series; losses never count as demand.

Before the cutover the system did not capture a loss reason, so every negative adjustment is an
"unclassified loss" and reasons expiry/damage/theft are not trusted. From the cutover on, expiry/damage/theft are
trusted and a negative adjustment without a structured reason is an "unspecified loss" (staff omitted it).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from demand.common import DEFAULT_CUTOVER, Mov

TRUSTED_LOSS_REASONS = ("expiry", "damage", "theft")
OTHER_FLOWS = {
    "adjustment_positive": "adjustment",
    "count_adjustment": "count",
    "transfer_in": "transfer",
    "transfer_out": "transfer",
    "purchase_receipt": "supplier_receipt",
    "return_supplier": "supplier_return",
    "production_consumption": "production",
    "production_output": "production",
    "initial_stock": "initial_stock",
}
DEMAND_REASONS = ("sale_shipment", "return_customer")


@dataclass(frozen=True)
class FlowRow:
    variant_id: int
    warehouse_id: int
    day: date
    flow: str
    qty: int


def classify(reason: str, day: date, cutover: date = DEFAULT_CUTOVER) -> str | None:
    """Flow name for a movement, or None when it is demand (handled by the demand provider)."""
    if reason in DEMAND_REASONS:
        return None
    if reason == "adjustment_negative":
        return "loss_unclassified" if day < cutover else "loss_unspecified"
    if reason in TRUSTED_LOSS_REASONS:
        return reason if day >= cutover else "loss_unclassified"
    return OTHER_FLOWS.get(reason, "other")


def flows_from_movements(movements: Iterable[Mov], cutover: date = DEFAULT_CUTOVER) -> list[FlowRow]:
    totals: dict[tuple[int, int, date, str], int] = defaultdict(int)
    for m in movements:
        if m.quarantined or m.day is None:
            continue
        flow = classify(m.reason, m.day, cutover)
        if flow is not None:
            totals[(m.variant_id, m.warehouse_id, m.day, flow)] += m.quantity
    return [FlowRow(v, w, d, f, q) for (v, w, d, f), q in sorted(totals.items())]
