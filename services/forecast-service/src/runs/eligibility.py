"""T059 logic: which policy applies to a product. Ineligible products get the conservative min/max and the reason."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from policies.base import Policy
from policies.estimators import BASELINE, POLICIES
from policies.fallback import NAME as FALLBACK


@dataclass(frozen=True)
class Decision:
    policy: str
    eligible: bool
    reasons: tuple[str, ...]


def decide(segment: dict[str, Any] | None, adopted: dict[str, str]) -> Decision:
    """``segment`` is the inventory-service classification (pattern, forecast_eligible, reasons)."""
    if segment is None:
        return Decision(FALLBACK, False, ("not_classified",))
    if not segment.get("forecast_eligible"):
        return Decision(FALLBACK, False, tuple(segment.get("reasons") or ("not_eligible",)))
    return Decision(adopted.get(segment["pattern"], BASELINE), True, ())


def policy_for(decision: Decision) -> Policy | None:
    return POLICIES.get(decision.policy)
