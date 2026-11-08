"""T097: refresh the export costs (and selling prices) in procurement after an inventory load (FR-037, research R16).

Only physical products are sent. Money travels as decimal strings, never floats. The target must be a local service and the call
uses the loader's own audience-scoped principal.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from . import guards
from .auth import loader_token
from .parse_inventory import InventoryItem

AUDIENCE = "api://mmi-procurement-service"
PushCosts = Callable[[list[dict[str, Any]], str], None]


FOUR = Decimal("0.0001")


def _money(d: Decimal | None) -> str | None:
    """Procurement stores four decimals; longer values from a spreadsheet are rounded half-up, never sent as they are."""
    return None if d is None else str(d if d == d.quantize(FOUR) else d.quantize(FOUR, rounding=ROUND_HALF_UP))


def build_cost_rows(items: dict[str, InventoryItem]) -> list[dict[str, Any]]:
    return [{"sku": i.sku, "export_cost": _money(i.cost), "pvp_gross": _money(i.pvp_gross), "tax_rate": _money(i.tax_rate),
             "tax_included": i.tax_included, "currency": i.currency}
            for i in items.values() if i.kind == "physical"]


def http_push_costs(procurement_url: str, transport: httpx.BaseTransport | None = None) -> PushCosts:
    url = guards.check_local_url(procurement_url).rstrip("/")

    def push(rows: list[dict[str, Any]], run_id: str) -> None:
        with httpx.Client(transport=transport, timeout=60) as client:
            for start in range(0, max(len(rows), 1), 5000):               # the endpoint accepts up to 20,000 rows; stay well below
                r = client.post(f"{url}/internal/export-costs", json={"load_run_id": run_id, "rows": rows[start:start + 5000]},
                                headers={"Authorization": f"Bearer {loader_token(AUDIENCE)}"})
                r.raise_for_status()

    return push
