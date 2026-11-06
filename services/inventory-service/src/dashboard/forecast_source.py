"""Forecast daily means for the coverage figure, read from forecast-service's latest run (eligible variants only)."""

from __future__ import annotations

from collections.abc import Callable

import httpx

HORIZON = "28"


class HttpForecastMeans:
    def __init__(self, base_url: str, token: str | Callable[[], str], client: httpx.Client | None = None) -> None:
        self._base, self._token, self._client = base_url.rstrip("/"), token, client or httpx.Client(timeout=15)

    def daily_means(self) -> dict[int, float]:
        token = self._token() if callable(self._token) else self._token
        r = self._client.get(f"{self._base}/forecasts/latest", headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 404:
            return {}                                                    # no run yet: the actual-demand basis is used and labelled
        r.raise_for_status()
        out: dict[int, float] = {}
        for vid, v in r.json()["variants"].items():
            h = v["horizons"].get(HORIZON)
            if v["eligible"] and h and h.get("mean") is not None:
                out[int(vid)] = float(h["mean"]) / int(HORIZON)
        return out

    def __repr__(self) -> str:
        return "HttpForecastMeans(token=***)"
