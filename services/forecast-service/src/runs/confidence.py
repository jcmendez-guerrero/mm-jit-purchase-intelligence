"""T044: how much to trust one product's forecast, from the quality of the history behind it (feature 018, FR-012, research R5).

Pure. Six flags, each a plain, testable condition on the series; the level follows from how many are set: none is ``alta``, one or two
``media``, three or more ``baja``. A per-product backtest result joins the rule once backtests exist (US4). The thresholds are defaults held
here because the business policy console stores none of them yet; they move there without changing the callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MIN_USABLE_DAYS = 90            # fewer usable (not stockout) days is a short history
SPARSE_PERCENT = 10             # fewer than this percentage of usable days with sales is sparse
STOCKOUT_PERCENT = 30           # more than this percentage of days without stock
EXCLUDED_PERCENT = 5            # more than this percentage of days a buyer excluded
ESTIMATED_PERCENT = 50          # more than this percentage of usable days estimated (seed days or a locally loaded series)
LOW_AT = 3                      # this many flags or more is low confidence


@dataclass(frozen=True)
class Confidence:
    level: str                  # "alta" | "media" | "baja"
    reasons: list[str]


def assess(s: dict[str, Any], seed_days: int = 0) -> Confidence:
    demand, censored = s["demand"], s["censored"]
    n = len(demand)
    stock_out = sum(1 for c in censored if c)
    usable = n - stock_out
    selling = sum(1 for d, c in zip(demand, censored, strict=True) if d > 0 and not c)
    estimated = usable if s.get("provenance", "observed") == "estimated" else min(seed_days, usable)
    excluded = int(s.get("anomaly_excluded_days", 0))
    flags: list[str] = []
    if usable < MIN_USABLE_DAYS:
        flags.append("short_history")
    if usable > 0 and selling * 100 < SPARSE_PERCENT * usable:
        flags.append("sparse_sales")
    if n > 0 and stock_out * 100 > STOCKOUT_PERCENT * n:
        flags.append("many_stockout_days")
    if n > 0 and excluded * 100 > EXCLUDED_PERCENT * n:
        flags.append("many_excluded_days")
    if usable > 0 and estimated * 100 > ESTIMATED_PERCENT * usable:
        flags.append("mostly_estimated")
    if (s.get("segment") or {}).get("xyz") == "Z":
        flags.append("high_variability")
    level = "baja" if len(flags) >= LOW_AT else "media" if flags else "alta"
    return Confidence(level, flags)
