"""T012 (FR-017, audit A24): money fields are shown only to roles allowed to see costs. A viewer gets counts and quantities; the money cards are hidden, not blank."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

MONEY_ROLES = frozenset({"buyer", "approver", "admin"})
MONEY_FIELDS = ("inventory_value", "expiring_value")


def can_see_money(roles: Iterable[str]) -> bool:
    return not MONEY_ROLES.isdisjoint(roles)


def hide_money(payload: dict[str, Any], roles: Iterable[str]) -> dict[str, Any]:
    """Returns the payload unchanged for cost-allowed roles; otherwise the money fields are removed and ``hidden_by_role`` names them."""
    if can_see_money(roles):
        return payload
    out = {k: v for k, v in payload.items() if k not in MONEY_FIELDS}
    out["hidden_by_role"] = [f for f in MONEY_FIELDS if f in payload]
    return out


MONEY_DRILL_KINDS = ("inventory_value", "abc_xyz")       # the figure of each row is an amount of money


def hide_cell_values(cells: list[dict[str, Any]], roles: Iterable[str]) -> list[dict[str, Any]]:
    """ABC/XYZ groups keep their product count; the value of the group is money."""
    return cells if can_see_money(roles) else [{k: v for k, v in c.items() if k != "value"} for c in cells]


def hide_money_page(page: dict[str, Any], roles: Iterable[str]) -> dict[str, Any]:
    """A drill-down behind a money figure still lists the products, but the amounts (row figures and the sum) are removed."""
    if can_see_money(roles) or page.get("kind") not in MONEY_DRILL_KINDS:
        return page
    return {**page, "sum": None, "rows": [{**r, "figure": None} for r in page["rows"]]}
