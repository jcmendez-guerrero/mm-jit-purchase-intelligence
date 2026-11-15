"""T060b: eligibility and confidence of every product in forecast-service's latest run, pulled over HTTP (feature 012, US5).

Same pattern as the dashboard's forecast means: a read-only call with a service token, so no event and no infrastructure change is needed.
No run yet means an empty answer and every product shows as ``pending`` in the portfolio, never as missing.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx


class HttpForecastEligibility:
    def __init__(self, base_url: str, token: str | Callable[[], str], client: httpx.Client | None = None) -> None:
        self._base, self._token, self._client = base_url.rstrip("/"), token, client or httpx.Client(timeout=30)

    def fetch(self) -> tuple[str | None, dict[str, tuple[str, str | None]]]:
        """(run id, sku -> (eligibility, confidence)); (None, {}) when there is no run yet."""
        token = self._token() if callable(self._token) else self._token
        r = self._client.get(f"{self._base}/forecasts/eligibility", headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 404:
            return None, {}
        r.raise_for_status()
        body = r.json()
        return body["run_id"], {v["sku"]: (v["eligibility"], v.get("confidence")) for v in body["variants"]}

    def __repr__(self) -> str:
        return "HttpForecastEligibility(token=***)"
