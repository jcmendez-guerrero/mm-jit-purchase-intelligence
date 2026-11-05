"""T055: data-quality metrics. The staff-training signal is the share of post-cutover negative adjustments
that carry no structured reason (adjustment_negative / (adjustment_negative + expiry + damage + theft))."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from demand.common import DEFAULT_CUTOVER, Mov
from demand.losses import TRUSTED_LOSS_REASONS

UNSPECIFIED_SHARE = "post_cutover_unspecified_loss_share"
QUARANTINED = "quarantined_movements"


def unspecified_loss_share(movements: Iterable[Mov], cutover: date = DEFAULT_CUTOVER) -> Decimal | None:
    """None when there are no post-cutover negative adjustments at all (nothing to measure)."""
    unspecified = structured = 0
    for m in movements:
        if m.quarantined or m.day is None or m.day < cutover:
            continue
        if m.reason == "adjustment_negative":
            unspecified += 1
        elif m.reason in TRUSTED_LOSS_REASONS:
            structured += 1
    total = unspecified + structured
    if total == 0:
        return None
    return (Decimal(unspecified) / Decimal(total)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def metrics(movements: list[Mov], cutover: date, day: date) -> dict[tuple[date, str], Decimal]:
    out: dict[tuple[date, str], Decimal] = {(day, QUARANTINED): Decimal(sum(1 for m in movements if m.quarantined))}
    share = unspecified_loss_share(movements, cutover)
    if share is not None:
        out[(day, UNSPECIFIED_SHARE)] = share
    return out
