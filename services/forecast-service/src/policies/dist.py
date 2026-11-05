"""Count-demand quantiles: Poisson when variance <= mean, negative binomial (method of moments) otherwise."""

from __future__ import annotations

import math


def _log_pmf_nb(k: int, r: float, p: float) -> float:
    return math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1) + r * math.log(p) + k * math.log(1 - p)


def quantile(mean: float, var: float, level: float) -> int:
    """Smallest integer q with P(D <= q) >= level. Deterministic; 0 for non-positive mean."""
    if not 0 < level < 1:
        raise ValueError("level must be strictly between 0 and 1")
    if mean <= 0:
        return 0
    cdf, k = 0.0, 0
    limit = int(mean + 12 * math.sqrt(max(var, mean))) + 60
    if var <= mean * 1.0001:
        term = math.exp(-mean)
        while k <= limit:
            cdf += term
            if cdf >= level:
                return k
            k += 1
            term *= mean / k
        return limit
    r = mean * mean / (var - mean)
    p = r / (r + mean)
    while k <= limit:
        cdf += math.exp(_log_pmf_nb(k, r, p))
        if cdf >= level:
            return k
        k += 1
    return limit
