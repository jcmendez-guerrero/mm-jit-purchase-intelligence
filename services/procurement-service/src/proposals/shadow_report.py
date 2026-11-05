"""T128: Shadow-mode evaluation report comparing proposals with actual buyer decisions and outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class ComparisonMetric:
    variant_id: int
    recommended_qty: int
    actual_qty: int
    qty_difference: int
    recommended_cost: Decimal
    actual_cost: Decimal
    cost_difference: Decimal
    overridden: bool
    stockout_occurred: bool


@dataclass
class ShadowReportSummary:
    total_variants_evaluated: int
    overridden_count: int
    override_rate: Decimal
    total_recommended_cost: Decimal
    total_actual_cost: Decimal
    cost_variance: Decimal
    stockout_incidents: int
    lines: list[ComparisonMetric]


def generate_shadow_report(
    recommendations: list[dict[str, Any]],
    actual_orders: list[dict[str, Any]],
    stockout_variants: set[int] | None = None,
) -> ShadowReportSummary:
    stockouts = stockout_variants or set()
    actual_by_var: dict[int, dict[str, Any]] = {
        o["variant_id"]: o for o in actual_orders
    }

    metrics: list[ComparisonMetric] = []
    total_rec_cost = Decimal("0.00")
    total_act_cost = Decimal("0.00")
    overridden_cnt = 0

    for rec in recommendations:
        var_id = rec["variant_id"]
        rec_qty = rec.get("recommended_qty", 0)
        rec_cost = Decimal(str(rec.get("recommended_cost", "0.00")))

        act = actual_by_var.get(var_id, {})
        act_qty = act.get("actual_qty", 0)
        act_cost = Decimal(str(act.get("actual_cost", "0.00")))

        diff_qty = act_qty - rec_qty
        diff_cost = act_cost - rec_cost
        is_overridden = diff_qty != 0
        if is_overridden:
            overridden_cnt += 1

        total_rec_cost += rec_cost
        total_act_cost += act_cost

        metrics.append(
            ComparisonMetric(
                variant_id=var_id,
                recommended_qty=rec_qty,
                actual_qty=act_qty,
                qty_difference=diff_qty,
                recommended_cost=rec_cost,
                actual_cost=act_cost,
                cost_difference=diff_cost,
                overridden=is_overridden,
                stockout_occurred=var_id in stockouts,
            )
        )

    n = len(recommendations)
    override_rate = (
        Decimal(overridden_cnt) / Decimal(n) if n > 0 else Decimal("0.00")
    )
    cost_variance = total_act_cost - total_rec_cost
    stockout_count = sum(1 for m in metrics if m.stockout_occurred)

    return ShadowReportSummary(
        total_variants_evaluated=n,
        overridden_count=overridden_cnt,
        override_rate=round(override_rate, 4),
        total_recommended_cost=total_rec_cost,
        total_actual_cost=total_act_cost,
        cost_variance=cost_variance,
        stockout_incidents=stockout_count,
        lines=metrics,
    )
