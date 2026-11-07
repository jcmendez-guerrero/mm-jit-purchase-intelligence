"""Forecast daily means for the coverage figure, read from forecast-service's latest run (eligible variants only)."""

from __future__ import annotations

from collections.abc import Callable

import httpx

HORIZON = "28"
UPPER = "0.95"


class HttpForecastMeans:
    def __init__(self, base_url: str, token: str | Callable[[], str], client: httpx.Client | None = None) -> None:
        self._base, self._token, self._client = base_url.rstrip("/"), token, client or httpx.Client(timeout=15)

    def _latest(self) -> dict[str, dict]:
        token = self._token() if callable(self._token) else self._token
        r = self._client.get(f"{self._base}/forecasts/latest", headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 404:
            return {}                                                    # no run yet: the actual-demand basis is used and labelled
        r.raise_for_status()
        return dict(r.json()["variants"])

    def daily_means(self) -> dict[int, float]:
        out: dict[int, float] = {}
        for vid, v in self._latest().items():
            h = v["horizons"].get(HORIZON)
            if v["eligible"] and h and h.get("mean") is not None:
                out[int(vid)] = float(h["mean"]) / int(HORIZON)
        return out

    def daily_bands(self) -> dict[int, tuple[float, float | None, bool]]:
        """(daily mean, daily upper bound at the 95 % level, rests on imported estimates) per forecast-eligible variant."""
        out: dict[int, tuple[float, float | None, bool]] = {}
        for vid, v in self._latest().items():
            h = v["horizons"].get(HORIZON)
            if v["eligible"] and h and h.get("mean") is not None:
                q = (h.get("quantiles") or {}).get(UPPER)
                out[int(vid)] = (float(h["mean"]) / int(HORIZON), None if q is None else float(q) / int(HORIZON), "seed_used" in (v.get("reasons") or []))
        return out

    def __repr__(self) -> str:
        return "HttpForecastMeans(token=***)"
