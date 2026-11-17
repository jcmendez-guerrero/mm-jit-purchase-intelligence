"""T020: historical coverage and gap days for one product over a period (feature 018, FR-002). Pure; no I/O."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Coverage:
    days_in_period: int
    days_with_data: int
    ratio: Decimal                          # days with data / days in period, six places
    gaps: list[tuple[date, date]]           # consecutive days without data, as inclusive ranges


def coverage(present: Iterable[date], start: date, end: date) -> Coverage:
    if end < start:
        raise ValueError("the period is empty")
    n = (end - start).days + 1
    have = {d for d in present if start <= d <= end}
    gaps: list[tuple[date, date]] = []
    run_start: date | None = None
    for i in range(n):
        d = start + timedelta(days=i)
        if d in have:
            if run_start is not None:
                gaps.append((run_start, d - timedelta(days=1)))
                run_start = None
        elif run_start is None:
            run_start = d
    if run_start is not None:
        gaps.append((run_start, end))
    ratio = (Decimal(len(have)) / Decimal(n)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return Coverage(n, len(have), ratio, gaps)
