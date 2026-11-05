"""T051: demand provider. Demand = customer sales shipped minus customer returns (ADR-012).

Sales carry negative quantities and returns positive ones, so both contribute ``-quantity``. Every other reason is
excluded here and lives in its own series (losses.py). Quarantined movements are excluded until reviewed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from demand.common import Mov, lineage

DEMAND_REASONS = ("sale_shipment", "return_customer")


@dataclass(frozen=True)
class DemandRow:
    variant_id: int
    warehouse_id: int
    day: date
    demand_qty: int
    lineage: str


class DemandProvider(Protocol):
    def daily_demand(self, movements: Iterable[Mov]) -> list[DemandRow]: ...


class MovementsDemandProvider:
    """Demand derived from stock movements (the business decision; tickets are not collected)."""

    def daily_demand(self, movements: Iterable[Mov]) -> list[DemandRow]:
        groups: dict[tuple[int, int, date], list[Mov]] = defaultdict(list)
        for m in movements:
            if m.reason in DEMAND_REASONS and not m.quarantined and m.day is not None:
                groups[(m.variant_id, m.warehouse_id, m.day)].append(m)
        return [
            DemandRow(v, w, d, -sum(m.quantity for m in ms), lineage(m.external_id for m in ms))
            for (v, w, d), ms in sorted(groups.items())
        ]
