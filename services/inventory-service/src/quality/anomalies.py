"""T021: deterministic anomaly rules for one product's daily demand (feature 012, FR-004, research R2). Pure; no I/O.

Rules, applied to days that are not stockout-censored:
* ``negative_qty``: a negative quantity (a net-return day); always flagged, whatever the history.
* ``mad_outlier``: the value is more than ``MAD_ABOVE`` robust deviations above the median of the non-zero, uncensored values
  of the trailing ``WINDOW`` days. The deviation is ``1.4826 * MAD`` floored at one unit, so a flat series (MAD zero) does not
  flag a one-unit step. Needs at least ``MIN_NONZERO`` such values in the window.
* ``p95_cap``: the value is above ``P95_FACTOR`` times the 95th percentile of the same window values.
Flags never change or remove the original value; the buyer's decision lives elsewhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from statistics import median

WINDOW = 90
MIN_NONZERO = 20
MAD_ABOVE = 5
MAD_SCALE = 1.4826
P95_FACTOR = 3


@dataclass(frozen=True)
class Anomaly:
    day: date
    rule_id: str
    original_value: int


def _percentile95(values: list[int]) -> float:
    ordered = sorted(values)
    idx = max(0, -(-95 * len(ordered) // 100) - 1)          # nearest-rank, no interpolation
    return float(ordered[idx])


def detect(days: Sequence[date], demand: Sequence[int], censored: Sequence[bool] | None = None) -> list[Anomaly]:
    if len(days) != len(demand):
        raise ValueError("days and demand differ in length")
    skip = list(censored) if censored is not None else [False] * len(demand)
    found: list[Anomaly] = []
    for i, value in enumerate(demand):
        if skip[i]:
            continue
        if value < 0:
            found.append(Anomaly(days[i], "negative_qty", value))
            continue
        lo = max(0, i - WINDOW)
        window = [v for v, c in zip(demand[lo:i], skip[lo:i], strict=True) if v > 0 and not c]
        if value <= 0 or len(window) < MIN_NONZERO:
            continue
        m = median(window)
        mad = median([abs(v - m) for v in window])
        if value - m > MAD_ABOVE * max(MAD_SCALE * mad, 1.0):
            found.append(Anomaly(days[i], "mad_outlier", value))
        if value > P95_FACTOR * _percentile95(window):
            found.append(Anomaly(days[i], "p95_cap", value))
    return found
