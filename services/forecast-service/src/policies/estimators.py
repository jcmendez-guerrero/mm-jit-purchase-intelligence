"""Rate estimators (the policy ladder). Pure functions of the censoring-free daily history."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from policies.base import VERSION


def _ses(values: Sequence[float], alpha: float, init: float) -> float:
    level = init
    for v in values:
        level += alpha * (v - level)
    return level


@dataclass(frozen=True)
class MinMaxPoisson:
    """Baseline: long-run mean rate. Everything else must beat this to be adopted."""

    name: str = "minmax_poisson"
    version: str = VERSION
    window_days: int = 365

    def rate(self, history: Sequence[int]) -> float | None:
        h = history[-self.window_days:]
        return sum(h) / len(h) if h else None


@dataclass(frozen=True)
class MovingAverage:
    name: str = "moving_average"
    version: str = VERSION
    weeks: int = 8

    def rate(self, history: Sequence[int]) -> float | None:
        n = self.weeks * 7
        if len(history) < n:
            return None
        return sum(history[-n:]) / n


@dataclass(frozen=True)
class SeasonalNaive:
    """Same period one year earlier. Needs more than a year of history, so it is simply unavailable until then."""

    name: str = "seasonal_naive"
    version: str = VERSION
    season_days: int = 364
    span_days: int = 28

    def rate(self, history: Sequence[int]) -> float | None:
        need = self.season_days + self.span_days
        if len(history) < need:
            return None
        start = len(history) - self.season_days
        window = history[start:start + self.span_days]
        return sum(window) / len(window)


@dataclass(frozen=True)
class CrostonSBA:
    """Croston with the Syntetos-Boylan bias correction: size / interval smoothed separately."""

    name: str = "croston_sba"
    version: str = VERSION
    alpha: float = 0.1

    def rate(self, history: Sequence[int]) -> float | None:
        sizes, gaps, last = [], [], -1
        for i, d in enumerate(history):
            if d > 0:
                sizes.append(float(d))
                gaps.append(float(i - last))
                last = i
        if not sizes:
            return 0.0 if history else None
        z = _ses(sizes[1:], self.alpha, sizes[0])
        p = _ses(gaps[1:], self.alpha, gaps[0])
        return (1 - self.alpha / 2) * z / p


@dataclass(frozen=True)
class TSB:
    """Teunter-Syntetos-Babai: smooths the probability of demand every period, so it decays for dying items."""

    name: str = "tsb"
    version: str = VERSION
    alpha: float = 0.1
    beta: float = 0.1

    def rate(self, history: Sequence[int]) -> float | None:
        if not history:
            return None
        first = next((d for d in history if d > 0), 0)
        prob = sum(1 for d in history if d > 0) / len(history)
        size = float(first) if first else 0.0
        prob = prob if first else 0.0
        started = False
        for d in history:
            if d > 0:
                size = float(d) if not started else size + self.alpha * (d - size)
                started = True
            prob += self.beta * ((1.0 if d > 0 else 0.0) - prob)
        return prob * size


@dataclass(frozen=True)
class ADIDA:
    """Aggregate to weeks, smooth, spread back to days."""

    name: str = "adida"
    version: str = VERSION
    bucket: int = 7
    alpha: float = 0.3

    def rate(self, history: Sequence[int]) -> float | None:
        n = len(history) // self.bucket
        if n < 4:
            return None
        trimmed = history[len(history) - n * self.bucket:]
        weekly = [float(sum(trimmed[i:i + self.bucket])) for i in range(0, len(trimmed), self.bucket)]
        return _ses(weekly[1:], self.alpha, weekly[0]) / self.bucket


BASELINE = "minmax_poisson"
CANDIDATES = (MinMaxPoisson(), MovingAverage(), SeasonalNaive(), CrostonSBA(), TSB(), ADIDA())
POLICIES = {p.name: p for p in CANDIDATES}
