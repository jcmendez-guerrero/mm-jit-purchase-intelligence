"""T078: which cost a proposal may use for a product-supplier pair.

A per-variant override beats the product-level (ERP) value. No cost -> the buyer must enter one first (FR-041).
An unconfirmed jump blocks use; a stale cost is usable but flagged so the buyer can verify it. Only supplier offers are
read here: last-paid history is never a candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Connection, Row

from costs.rules import CostRules
from costs.store import cost_status, current


@dataclass(frozen=True)
class Resolution:
    cost: Row[Any] | None
    usable: bool
    status: str                      # ok / stale / blocked_jump / cost_required
    warnings: list[str] = field(default_factory=list)
    needs_entry: bool = False
    from_variant_override: bool = False


def resolve_cost(conn: Connection, product_id: int, supplier_id: str, rules: CostRules, variant_id: int | None = None,
                 now: datetime | None = None) -> Resolution:
    now = now or datetime.now(UTC)
    override = current(conn, product_id, supplier_id, variant_id) if variant_id is not None else None
    row = override or current(conn, product_id, supplier_id, None)
    if row is None:
        return Resolution(None, False, "cost_required", ["cost_required"], needs_entry=True)
    st = cost_status(row, rules, now)
    return Resolution(row, st != "blocked_jump", st, [st] if st != "ok" else [], from_variant_override=override is not None)
