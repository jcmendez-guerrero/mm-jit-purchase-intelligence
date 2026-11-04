"""Policy ladder: estimators of the mean daily demand rate, plus the shared min/max plan builder.

Every candidate differs only in how it estimates the rate; the plan (reorder point, order-up-to level, uncertainty)
is built the same way so backtests compare like with like. Censored days (stock-outs) are removed from the history
before estimation so a stock-out is never learned as zero demand.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean, variance
from typing import Protocol

from policies.dist import quantile

VERSION = "1.0.0"
LEVELS = (0.85, 0.90, 0.95, 0.97, 0.99)


class Policy(Protocol):
    name: str
    version: str

    def rate(self, history: Sequence[int]) -> float | None:
        """Mean daily demand, or None when the policy cannot be applied to this history."""


@dataclass(frozen=True)
class Plan:
    policy: str
    rate: float
    mean_horizon: float
    var_horizon: float
    reorder_point: int      # demand over the lead time at the service level (the "min")
    order_up_to: int        # demand over the protection horizon at the service level (the "max")
    safety_stock: int
    quantiles: dict[str, int]


def prepare_history(demand: Sequence[int], censored: Sequence[bool] | None = None) -> list[int]:
    """Drop censored days; returns plain non-negative integers (a net-return day counts as zero)."""
    if censored is None:
        return [max(0, d) for d in demand]
    return [max(0, d) for d, c in zip(demand, censored, strict=True) if not c]


def horizon_variance(history: Sequence[int], horizon: int, rate: float) -> float:
    """Variance of demand over the horizon: the larger of Poisson (= mean) and the sample variance of
    non-overlapping horizon-length sums, rescaled to the policy's own rate."""
    mean_h = rate * horizon
    sums = [sum(history[i:i + horizon]) for i in range(0, len(history) - horizon + 1, horizon)]
    if len(sums) < 4:
        return mean_h
    hist_mean = fmean(sums)
    sample_var = variance(sums)
    scale = rate * horizon / hist_mean if hist_mean > 0 else 1.0
    return max(mean_h, sample_var * scale)


def build_plan(policy: str, rate: float, history: Sequence[int], horizon: int, lead_time: int, service_level: float,
               extra_dispersion: float = 1.0) -> Plan:
    rate = max(rate, 0.0)
    mean_h = rate * horizon
    var_h = horizon_variance(history, horizon, rate) * extra_dispersion
    mean_l = rate * lead_time
    var_l = var_h * (lead_time / horizon) if horizon else mean_l
    order_up_to = quantile(mean_h, var_h, service_level)
    return Plan(
        policy=policy, rate=rate, mean_horizon=mean_h, var_horizon=var_h,
        reorder_point=quantile(mean_l, max(var_l, mean_l), service_level) if lead_time > 0 else 0,
        order_up_to=order_up_to, safety_stock=max(0, order_up_to - math.ceil(mean_h)),
        quantiles={f"{lv:.2f}": quantile(mean_h, var_h, lv) for lv in sorted({*LEVELS, round(service_level, 4)})},
    )
