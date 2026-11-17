"""T034: why a forecast is what it is - class, method and the reason for it, eligibility, censored days and provenance (feature 018).

Pure: it turns one series, the eligibility decision and the run's versions into the row stored in ``forecast_explanations``. The same
input always gives the same row. A product that is not eligible gets no forecast figure, only the fallback and its reason codes.
The range (low, expected, high) and the confidence label come from the plan and from ``runs.confidence``. A product whose confidence is low is
published like a not-eligible one (min/max, no figure) and shows as ``manual_review_only``.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from runs.confidence import assess
from runs.eligibility import Decision

Z90 = 1.2816            # one-sided 90 % point of the normal curve: the low end of the range is the mean minus this many deviations

INTERMITTENT_PATTERNS = frozenset({"intermittent", "lumpy"})


def _method_reason(decision: Decision, policy_used: str, adopted: dict[str, str], pattern: str | None) -> str:
    if not decision.eligible:
        return "min_max_fallback"
    if policy_used != decision.policy:
        return "method_fallback_to_baseline"       # the chosen method had too little history to run
    if pattern is not None and adopted.get(pattern) == policy_used:
        return "backtest_adopted"
    return "baseline_default"


def _range(mean: float, plan: Any) -> tuple[float, float]:
    """Low is the mean less 1.28 deviations (never below zero); high is the plan's 90th percentile. The expected figure always sits between them."""
    sd = math.sqrt(max(float(plan.var_horizon), 0.0))
    high = float(plan.quantiles.get("0.90", mean + Z90 * sd))
    return round(min(max(0.0, mean - Z90 * sd), mean), 4), round(max(high, mean), 4)


def explain(s: dict[str, Any], decision: Decision, policy_used: str, mean: float | None, adopted: dict[str, str], versions: dict[str, str],
            dataset_version_id: str | None, seed_days: int = 0, plan: Any = None) -> dict[str, Any]:
    seg = s.get("segment") or {}
    pattern = seg.get("pattern")
    n = len(s["demand"])
    start = date.fromisoformat(s["start_day"])
    censored = sum(1 for c in s["censored"] if c)
    usable = n - censored
    seed = min(seed_days, usable)
    own = usable - seed
    label = s.get("provenance", "observed")           # a locally loaded or imputed series is never counted as observed
    mix = {"observed": own if label == "observed" else 0, "estimated": seed + (own if label == "estimated" else 0), "manual": own if label == "manual" else 0}
    low_confidence = "low_confidence" in decision.reasons            # published like a not-eligible product: the min/max fallback and no figure
    confidence = assess(s, seed) if (decision.eligible or low_confidence) else None
    eligible_figure = decision.eligible and mean is not None
    low, high = _range(mean, plan) if eligible_figure and plan is not None and mean is not None else (None, None)
    eligibility = "manual_review_only" if low_confidence else "eligible" if decision.eligible else "not_eligible"
    return {
        "sku": s.get("sku"),
        "model_version": f"{policy_used}@{versions.get(policy_used, 'unknown')}",
        "dataset_version_id": dataset_version_id,
        "config_version_id": seg.get("config_version_id"),
        "history_start": start.isoformat(),
        "history_end": (start + timedelta(days=n - 1)).isoformat(),
        "abc": seg.get("abc"),
        "xyz": seg.get("xyz"),
        "pattern": pattern,
        "intermittent": pattern in INTERMITTENT_PATTERNS,
        "method": policy_used,
        "method_reason_code": _method_reason(decision, policy_used, adopted, pattern),
        "censored_days": censored,
        "anomaly_days_excluded": int(s.get("anomaly_excluded_days", 0)),
        "provenance_mix": mix,
        "low": low,
        "expected": round(mean, 4) if eligible_figure and mean is not None else None,
        "high": high,
        "confidence": confidence.level if confidence else None,
        "confidence_reason_codes": confidence.reasons if confidence else [],
        "eligibility": eligibility,
        "eligibility_reason_codes": list(decision.reasons),
    }
