"""T066: rolling-origin backtests scored in money terms (stock-out, holding and expiry cost), per segment.

At each origin the policy sees only the history before it, sets an order-up-to level for the protection horizon, and is
compared with what was actually sold afterwards: demand above the level is a stock-out, stock above demand is
holding cost plus an expiry-loss share. A more complex method is adopted for a segment only when it beats the baseline
by a margin over enough windows; otherwise the baseline stays. Windows dominated by stock-outs are skipped because
the true demand cannot be observed there.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from policies.base import Policy, build_plan, prepare_history
from policies.estimators import BASELINE


@dataclass(frozen=True)
class CostModel:
    stockout_multiplier: Decimal = Decimal("1.0")         # lost sale costs this multiple of the unit price
    holding_rate_per_year: Decimal = Decimal("0.22")      # capital + storage as a share of unit value per year
    expiry_loss_fraction: Decimal = Decimal("0.02")       # share of leftover value assumed lost; refine with lot expiry data


@dataclass(frozen=True)
class BacktestConfig:
    horizon: int = 14                 # protection horizon: review period + typical lead time
    lead_time: int = 7
    origins: int = 12
    step: int = 7
    min_history: int = 56
    max_censored_share: float = 0.5
    min_gain: Decimal = Decimal("0.05")
    min_windows: int = 30
    costs: CostModel = field(default_factory=CostModel)


@dataclass(frozen=True)
class BacktestSeries:
    variant_id: int
    demand: Sequence[int]
    censored: Sequence[bool]
    price: Decimal
    segment: str
    service_level: float


@dataclass
class Cost:
    stockout: Decimal = Decimal(0)
    holding: Decimal = Decimal(0)
    expiry: Decimal = Decimal(0)
    windows: int = 0

    @property
    def total(self) -> Decimal:
        return self.stockout + self.holding + self.expiry

    def add(self, other: Cost) -> None:
        self.stockout += other.stockout
        self.holding += other.holding
        self.expiry += other.expiry
        self.windows += other.windows


def backtest_series(s: BacktestSeries, policy: Policy, cfg: BacktestConfig) -> Cost:
    cost = Cost()
    n = len(s.demand)
    for k in range(cfg.origins):
        t = n - cfg.horizon - (cfg.origins - 1 - k) * cfg.step
        if t < cfg.min_history:
            continue
        window_cens = s.censored[t:t + cfg.horizon]
        if sum(window_cens) / cfg.horizon > cfg.max_censored_share:
            continue
        history = prepare_history(s.demand[:t], s.censored[:t])
        rate = policy.rate(history)
        if rate is None:
            continue
        plan = build_plan(policy.name, rate, history, cfg.horizon, cfg.lead_time, s.service_level)
        actual = sum(max(0, d) for d, c in zip(s.demand[t:t + cfg.horizon], window_cens, strict=True) if not c)
        under, over = max(actual - plan.order_up_to, 0), max(plan.order_up_to - actual, 0)
        c = cfg.costs
        cost.stockout += Decimal(under) * s.price * c.stockout_multiplier
        cost.holding += Decimal(over) * s.price * c.holding_rate_per_year * Decimal(cfg.horizon) / Decimal(365)
        cost.expiry += Decimal(over) * s.price * c.expiry_loss_fraction
        cost.windows += 1
    return cost


Results = dict[str, dict[str, Cost]]   # segment -> policy -> cost


def compare(series: Iterable[BacktestSeries], policies: Iterable[Policy], cfg: BacktestConfig | None = None) -> Results:
    cfg = cfg or BacktestConfig()
    policies = list(policies)
    out: Results = defaultdict(lambda: defaultdict(Cost))
    for s in series:
        for p in policies:
            out[s.segment][p.name].add(backtest_series(s, p, cfg))
    return {seg: dict(per) for seg, per in out.items()}


def select_policies(results: Results, cfg: BacktestConfig | None = None, baseline: str = BASELINE) -> dict[str, str]:
    """Per segment: the cheapest policy, adopted only if it beats the baseline by ``min_gain`` over ``min_windows``."""
    cfg = cfg or BacktestConfig()
    chosen: dict[str, str] = {}
    for seg, per in results.items():
        base = per.get(baseline)
        chosen[seg] = baseline
        if base is None or base.windows < cfg.min_windows:
            continue
        best_name, best = min(((n, c) for n, c in per.items() if n != baseline and c.windows >= cfg.min_windows),
                              key=lambda nc: (nc[1].total, nc[0]), default=(None, None))
        if best is not None and best_name is not None and best.total <= base.total * (1 - cfg.min_gain):
            chosen[seg] = best_name
    return chosen
