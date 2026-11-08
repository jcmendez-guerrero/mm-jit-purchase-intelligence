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
