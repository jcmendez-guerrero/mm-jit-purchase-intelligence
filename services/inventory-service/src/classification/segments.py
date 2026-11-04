"""T063: ABC / XYZ / demand-pattern classification and forecast eligibility. Pure functions, no I/O.

* Time is bucketed in 7-day blocks ending at ``through_day`` (daily retail demand is too sparse for daily statistics).
  Blocks where stock was at or below zero on most days are censored and excluded from the statistics.
* Pattern follows Syntetos-Boylan on the blocks: ADI (blocks per non-zero block) against 1.32 and CV^2 of non-zero
  block sizes against 0.49. Smooth / intermittent / lumpy are the three non-trivial classes; "erratic" (frequent but
  highly variable) is treated as lumpy. ``new`` and ``discontinued`` take precedence.
* XYZ is the coefficient of variation of the block series: X < 0.5, Y < 1.0, Z otherwise.
* ABC ranks selling value over the window: A is the top 80 % of cumulative value, B the next 15 %, C the rest.
* A product that cannot be forecast honestly is not eligible and says why (reason codes); it falls back to min/max.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from statistics import fmean, pstdev

BLOCK_DAYS = 7


@dataclass(frozen=True)
class ClassificationConfig:
    adi_cutoff: float = 1.32
    cv2_cutoff: float = 0.49
    xyz_x: float = 0.5
    xyz_y: float = 1.0
    abc_a: float = 0.80
    abc_b: float = 0.95
    new_after_days: int = 90          # fewer days of history than this => "new"
    min_nonzero_blocks: int = 8       # fewer selling weeks than this => too sparse to forecast
    max_censored_share: float = 0.5
    censored_block_days: int = 4      # a block with this many censored days is excluded


@dataclass(frozen=True)
class SeriesInput:
    variant_id: int
    days: list[date]            # consecutive days, oldest first, ending at through_day
    demand: list[int]           # same length as days (0 on days without sales)
    censored: list[bool]        # stock at or below zero
    price: Decimal
    product_discontinued: bool = False
    history_reconciled: bool = True
    pending_review: bool = False


@dataclass(frozen=True)
class Segment:
    variant_id: int
    abc: str
    xyz: str
    pattern: str
    eligible: bool
    reasons: list[str]
    metrics: dict[str, float | int | str | None] = field(default_factory=dict)


def blocks(s: SeriesInput, cfg: ClassificationConfig) -> tuple[list[int], int]:
    """(demand per usable block, number of censored blocks). Leading partial days are dropped."""
    n = len(s.demand)
    usable: list[int] = []
    censored_blocks = 0
    for end in range(n, BLOCK_DAYS - 1, -BLOCK_DAYS):
        start = end - BLOCK_DAYS
        if sum(s.censored[start:end]) >= cfg.censored_block_days:
            censored_blocks += 1
        else:
            usable.append(sum(s.demand[start:end]))
    usable.reverse()
    return usable, censored_blocks


def _cv(values: list[int]) -> float:
    if not values:
        return math.inf
    mean = fmean(values)
    return pstdev(values) / mean if mean > 0 else math.inf


def pattern_stats(usable: list[int]) -> tuple[float, float]:
    """(ADI, CV^2 of non-zero sizes). ADI is inf when nothing sold."""
    nonzero = [v for v in usable if v > 0]
    if not nonzero:
        return math.inf, 0.0
    adi = len(usable) / len(nonzero)
    mean = fmean(nonzero)
    return adi, (pstdev(nonzero) / mean) ** 2 if mean > 0 else 0.0


def classify_series(s: SeriesInput, abc: str, cfg: ClassificationConfig | None = None) -> Segment:
    cfg = cfg or ClassificationConfig()
    usable, censored_blocks = blocks(s, cfg)
    total_blocks = len(usable) + censored_blocks
    nonzero = sum(1 for v in usable if v > 0)
    adi, cv2 = pattern_stats(usable)
    cv = _cv(usable)
    xyz = "X" if cv < cfg.xyz_x else "Y" if cv < cfg.xyz_y else "Z"
    history_days = len(s.days)
    if s.product_discontinued:
        pattern = "discontinued"
    elif history_days < cfg.new_after_days:
        pattern = "new"
    elif adi < cfg.adi_cutoff and cv2 < cfg.cv2_cutoff:
        pattern = "smooth"
    elif adi >= cfg.adi_cutoff and cv2 < cfg.cv2_cutoff:
        pattern = "intermittent"
    else:
        pattern = "lumpy"  # includes erratic: frequent but highly variable
    censored_share = censored_blocks / total_blocks if total_blocks else 0.0
    reasons: list[str] = []
    if pattern == "discontinued":
        reasons.append("discontinued")
    if pattern == "new":
        reasons.append("new")
    if not s.history_reconciled:
        reasons.append("history_unreconciled")
    if s.pending_review:
        reasons.append("pending_review")
    if pattern not in ("discontinued", "new") and nonzero < cfg.min_nonzero_blocks:
        reasons.append("too_sparse")
    if censored_share > cfg.max_censored_share:
        reasons.append("mostly_censored")
    metrics: dict[str, float | int | str | None] = {
        "adi": None if math.isinf(adi) else round(adi, 3), "cv2": round(cv2, 3), "cv": None if math.isinf(cv) else round(cv, 3),
        "blocks": len(usable), "nonzero_blocks": nonzero, "censored_blocks": censored_blocks,
        "censored_share": round(censored_share, 3), "history_days": history_days,
    }
    return Segment(s.variant_id, abc, xyz, pattern, not reasons, reasons, metrics)


def assign_abc(values: dict[int, Decimal], cfg: ClassificationConfig | None = None) -> dict[int, str]:
    """A / B / C by cumulative selling value; zero-value items are C. Deterministic for ties (by variant id)."""
    cfg = cfg or ClassificationConfig()
    positive = {k: v for k, v in values.items() if v > 0}
    total = sum(positive.values(), Decimal(0))
    out = dict.fromkeys(values, "C")
    if total <= 0:
        return out
    running = Decimal(0)
    for vid, value in sorted(positive.items(), key=lambda kv: (-kv[1], kv[0])):
        before = running / total  # an item is A if it starts inside the top 80 % of value
        running += value
        out[vid] = "A" if before < Decimal(str(cfg.abc_a)) else "B" if before < Decimal(str(cfg.abc_b)) else "C"
    return out


def series_value(s: SeriesInput) -> Decimal:
    return max(Decimal(sum(s.demand)), Decimal(0)) * s.price
