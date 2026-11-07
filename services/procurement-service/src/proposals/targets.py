"""T091: replenishment targets. Protection horizon H = 7 days + the supplier's lead time.

order-up-to and reorder point come from the forecast quantile at the service level (or the conservative min/max when the
product is not forecast-eligible), interpolated between the stored horizons. Inventory position counts usable on-hand
(minus lots expiring before the horizon ends) plus inbound orders arriving within the horizon. An order is needed only
when the position is at or below the reorder point; the quantity brings the position back to the order-up-to level.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from proposals.model import REVIEW_DAYS, Forecast, VariantInput


@dataclass(frozen=True)
class Target:
    variant_id: int
    horizon_days: int
    lead_time_days: int
    expected_demand: float | None
    order_up_to: int
    reorder_point: int
    safety_stock: int | None
    on_hand: int
    expiring_qty: int
    usable_on_hand: int
    inbound_counted: int
    inventory_position: int
    need: int
    policy: str
    fallback: bool
    service_level: Decimal
    floor_reason: str | None = None
    estimate_based: bool = False            # the forecast rests on imported estimates (FR-008): shown as a label, never changes a quantity


def _interp(points: list[tuple[int, float]], h: float) -> float:
    """Piecewise-linear through (0, 0) and the stored horizons; proportional beyond the last one (conservative)."""
    pts = [(0, 0.0), *sorted(points)]
    for (h0, v0), (h1, v1) in pairwise(pts):
        if h <= h1:
            return v0 + (v1 - v0) * (h - h0) / (h1 - h0)
    last_h, last_v = pts[-1]
    return last_v * h / last_h if last_h else 0.0


def _level_key(quantiles: dict[str, int], level: Decimal) -> str:
    want = f"{float(level):.2f}"
    if want in quantiles:
        return want
    higher = sorted(k for k in quantiles if k.replace(".", "", 1).isdigit() and float(k) >= float(level))
    return higher[0] if higher else max((k for k in quantiles if k.replace(".", "", 1).isdigit()), key=float)


def _quantile_at(fc: Forecast, horizon: float, level: Decimal) -> float:
    if fc.eligible:
        pts = [(h, float(hf.quantiles[_level_key(hf.quantiles, level)])) for h, hf in fc.horizons.items() if hf.quantiles]
    else:
        pts = [(h, float(hf.quantiles["max"])) for h, hf in fc.horizons.items() if "max" in hf.quantiles]
    return _interp(pts, horizon) if pts else 0.0


def _reorder_at(fc: Forecast, horizon: float, lead: float, level: Decimal) -> float:
    if fc.eligible:
        return _quantile_at(fc, lead, level)
    pts = [(h, float(hf.quantiles["min"])) for h, hf in fc.horizons.items() if "min" in hf.quantiles]
    return _interp(pts, horizon) if pts else 0.0


def compute_target(v: VariantInput, lead_time_days: int) -> Target:
    horizon = REVIEW_DAYS + lead_time_days
    fc = v.forecast
    up_to = math.ceil(_quantile_at(fc, horizon, v.service_level) - 1e-9)
    reorder = min(math.ceil(_reorder_at(fc, horizon, lead_time_days, v.service_level) - 1e-9), up_to)
    mean_pts = [(h, hf.mean) for h, hf in fc.horizons.items() if hf.mean is not None]
    mean = _interp([(h, float(m)) for h, m in mean_pts], horizon) if fc.eligible and mean_pts else None
    mean_ceil = None if mean is None else math.ceil(mean - 1e-9)
    if v.safety_override is not None:                      # approved override replaces the recommended safety stock
        up_to = (mean_ceil + v.safety_override) if mean_ceil is not None else max(up_to, v.safety_override)
        reorder = min(reorder, up_to)
    if v.min_units:
        up_to, reorder = max(up_to, v.min_units), max(reorder, v.min_units)
    if v.max_units is not None:
        up_to = min(up_to, v.max_units)
        reorder = min(reorder, up_to)
    usable = max(v.on_hand - v.expiring_qty, 0)
    inbound = sum(q for q, eta in v.inbound if eta <= horizon)
    position = usable + inbound
    need = max(up_to - position, 0) if position <= reorder else 0
    if v.clinical_critical and position < 1 and up_to >= 1:
        need = max(need, 1)
    floor_reason = None
    if v.floor_units > 0 and position + need < v.floor_units:       # always-stocked: never below the floor, whatever the demand
        need, floor_reason = v.floor_units - position, "always_stocked_floor"
    elif v.monthly_check and need == 0:                               # nothing bought for a month: at least one unit
        need, floor_reason = 1, "always_stocked_monthly"
    return Target(
        v.variant_id, horizon, lead_time_days, mean, up_to, reorder, None if mean is None else max(0, up_to - math.ceil(mean)),
        v.on_hand, v.expiring_qty, usable, inbound, position, need, fc.policy, not fc.eligible, v.service_level, floor_reason, fc.eligible and "seed_used" in fc.reasons)
