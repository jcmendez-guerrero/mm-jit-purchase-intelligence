"""T063: margin rules for a supplier-cost update (FR-043). Decimal only; comparisons are exact (no rounding before deciding).

margin = 1 - cost / PVP, with the Recargo-inclusive cost. The maximum margin is 30 % when the cost is below EUR 50 and 20 % when it
is EUR 50 or more (the threshold applies to the cost being evaluated). Rules (a)-(c) flag and explain; (d) blocks below 15 %.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

THRESHOLD = Decimal("50")
CAP_BELOW, CAP_FROM = Decimal("0.30"), Decimal("0.20")
MINIMUM = Decimal("0.15")
Q4 = Decimal("0.0001")

KEPT_OFFER = "margin_kept_offer"
ABOVE_CAP = "margin_above_cap"
BELOW_MINIMUM = "margin_below_minimum"
UNAVAILABLE = "margin_unavailable"
PVP_STALE = "pvp_stale"


def cap_for(cost: Decimal) -> Decimal:
    return CAP_BELOW if cost < THRESHOLD else CAP_FROM


def margin_of(cost: Decimal, pvp: Decimal | None) -> Decimal | None:
    if pvp is None or pvp <= 0:
        return None
    return (1 - cost / pvp).quantize(Q4, rounding=ROUND_HALF_UP)


def cost_for_margin(pvp: Decimal, margin: Decimal) -> Decimal:
    """The Recargo-inclusive cost that yields exactly this margin: PVP x (1 - margin)."""
    return (pvp * (1 - margin)).quantize(Q4, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Evaluation:
    pvp: Decimal | None
    margin_before: Decimal | None
    margin_after: Decimal | None
    cap: Decimal
    flags: tuple[str, ...] = field(default_factory=tuple)
    blocked: bool = False
    cost_at_minimum: Decimal | None = None      # tips: the cost that yields exactly 15 % and the cap
    cost_at_cap: Decimal | None = None
    pvp_age_days: int | None = None             # days since a sync last confirmed the price; None when unknown


def evaluate(new_cost: Decimal, previous_cost: Decimal | None, pvp: Decimal | None) -> Evaluation:
    for v in (new_cost, previous_cost, pvp):
        if isinstance(v, float):
            raise TypeError("floats are not allowed for money")
    cap = cap_for(new_cost)
    if pvp is None or pvp <= 0:
        return Evaluation(None, None, None, cap, (UNAVAILABLE,), False)
    floor_cost = pvp * (1 - MINIMUM)            # cost at exactly 15 %: anything above blocks
    cap_cost = pvp * (1 - cap)                  # cost at exactly the cap: anything below exceeds it
    flags: list[str] = []
    if new_cost < cap_cost:                                            # margin after > cap
        already = previous_cost is not None and previous_cost <= cap_cost
        flags.append(KEPT_OFFER if already else ABOVE_CAP)
    blocked = new_cost > floor_cost
    if blocked:
        flags.append(BELOW_MINIMUM)
    return Evaluation(pvp, None if previous_cost is None else margin_of(previous_cost, pvp), margin_of(new_cost, pvp), cap, tuple(flags), blocked,
                      cost_for_margin(pvp, MINIMUM), cost_for_margin(pvp, cap))
