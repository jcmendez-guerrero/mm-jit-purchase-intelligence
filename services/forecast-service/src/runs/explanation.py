"""T034: why a forecast is what it is - class, method and the reason for it, eligibility, censored days and provenance (feature 012).

Pure: it turns one series, the eligibility decision and the run's versions into the row stored in ``forecast_explanations``. The same
input always gives the same row. A product that is not eligible gets no forecast figure, only the fallback and its reason codes.
Range (low, high) and confidence are added in the next story (T044); here they stay empty.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from runs.eligibility import Decision

INTERMITTENT_PATTERNS = frozenset({"intermittent", "lumpy"})


def _method_reason(decision: Decision, policy_used: str, adopted: dict[str, str], pattern: str | None) -> str:
    if not decision.eligible:
        return "min_max_fallback"
    if policy_used != decision.policy:
        return "method_fallback_to_baseline"       # the chosen method had too little history to run
    if pattern is not None and adopted.get(pattern) == policy_used:
        return "backtest_adopted"
    return "baseline_default"


def explain(s: dict[str, Any], decision: Decision, policy_used: str, mean: float | None, adopted: dict[str, str], versions: dict[str, str],
            dataset_version_id: str | None, seed_days: int = 0) -> dict[str, Any]:
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
        "low": None,
        "expected": round(mean, 4) if decision.eligible and mean is not None else None,
        "high": None,
        "confidence": None,
        "confidence_reason_codes": [],
        "eligibility": "eligible" if decision.eligible else "not_eligible",
        "eligibility_reason_codes": list(decision.reasons),
    }
