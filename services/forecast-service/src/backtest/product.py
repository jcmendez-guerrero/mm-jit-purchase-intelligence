"""T053: how well one product's method would have forecast what really sold, against the baseline (feature 018, FR-016, FR-018).

Pure. It reuses the rolling-origin windows of ``backtest.runner``: at each origin the method (and the baseline) see only the history before it
and forecast the next ``horizon`` days; the forecast is compared with the demand that was really observed. Windows dominated by stockout days are
skipped, and the forecast is scaled to the observable share of a window, so a stockout is never read as zero demand. WAPE is the total absolute
error over the total demand; bias is the signed error over the total demand (positive is over-forecasting). Where there is nothing to compare
(no window, or no sales) the result says so and the product is not flagged.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from policies.base import Policy, build_plan, prepare_history
from policies.estimators import BASELINE, POLICIES

from backtest.runner import BacktestConfig

SIX = Decimal("0.000001")


@dataclass(frozen=True)
class ProductBacktest:
    periods: int
    wape: Decimal | None
    bias: Decimal | None
    baseline_wape: Decimal | None
    baseline_bias: Decimal | None
    beats_baseline: bool          # False only when there is evidence the method does worse than the baseline


def _mean(policy: Policy, fallback: Policy, history: list[int], horizon: int, lead_time: int, level: float) -> float:
    rate = policy.rate(history)
    if rate is None:
        rate = fallback.rate(history)
    return build_plan(policy.name, rate or 0.0, history, horizon, lead_time, level).mean_horizon


def _q(x: float) -> Decimal:
    return Decimal(str(round(x, 6))).quantize(SIX, rounding=ROUND_HALF_UP)


def backtest_product(s: dict[str, Any], method: str, cfg: BacktestConfig | None = None) -> ProductBacktest:
    cfg = cfg or BacktestConfig()
    demand, censored, level = s["demand"], s["censored"], float(s["service_level"])
    base = POLICIES[BASELINE]
    policy = POLICIES.get(method, base)
    n = len(demand)
    actual = m_abs = m_err = b_abs = b_err = 0.0
    periods = 0
    for k in range(cfg.origins):
        t = n - cfg.horizon - (cfg.origins - 1 - k) * cfg.step
        if t < cfg.min_history:
            continue
        window = censored[t:t + cfg.horizon]
        if sum(window) / cfg.horizon > cfg.max_censored_share:
            continue
        history = prepare_history(demand[:t], censored[:t])
        share = (cfg.horizon - sum(window)) / cfg.horizon
        real = float(sum(max(0, d) for d, c in zip(demand[t:t + cfg.horizon], window, strict=True) if not c))
        mf = _mean(policy, base, history, cfg.horizon, cfg.lead_time, level) * share
        bf = _mean(base, base, history, cfg.horizon, cfg.lead_time, level) * share
        actual += real
        m_abs += abs(mf - real)
        m_err += mf - real
        b_abs += abs(bf - real)
        b_err += bf - real
        periods += 1
    if periods == 0 or actual <= 0:
        return ProductBacktest(periods, None, None, None, None, True)
    wape, baseline_wape = _q(m_abs / actual), _q(b_abs / actual)
    return ProductBacktest(periods, wape, _q(m_err / actual), baseline_wape, _q(b_err / actual), wape <= baseline_wape)
