"""Conservative min/max used when a product is not forecast-eligible. No forecast is published for it."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from policies.base import Plan, build_plan

NAME = "minmax_conservative"


@dataclass(frozen=True)
class ConservativeResult:
    plan: Plan
    note: str


def conservative_plan(history: Sequence[int], horizon: int, lead_time: int, service_level: float, clinical_critical: bool = False,
                      recent_days: int = 56) -> ConservativeResult:
    """Rate is the higher of the long-run and the recent mean, with doubled dispersion; a clinically critical product
    that has ever sold keeps at least one unit of cover. Nothing here pretends to be a forecast."""
    long_run = sum(history) / len(history) if history else 0.0
    recent = history[-recent_days:]
    recent_rate = sum(recent) / len(recent) if recent else 0.0
    plan = build_plan(NAME, max(long_run, recent_rate), history, horizon, lead_time, service_level, extra_dispersion=2.0)
    if clinical_critical and any(history) and plan.order_up_to < 1:
        plan = Plan(plan.policy, plan.rate, plan.mean_horizon, plan.var_horizon, max(plan.reorder_point, 1), 1, 1, plan.quantiles)
    return ConservativeResult(plan, "min_max_fallback")
