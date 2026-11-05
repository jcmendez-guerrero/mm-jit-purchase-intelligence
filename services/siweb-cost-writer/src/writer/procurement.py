"""The writer re-checks every request with procurement-service (service identity) before it touches the ERP."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import httpx


class ProcurementApi(Protocol):
    def get_released(self, request_id: str) -> dict[str, Any] | None:
        """The request as released by the buyer, or None when it does not exist or was not released."""


class HttpProcurementApi:
    def __init__(self, base_url: str, token: str | Callable[[], str], client: httpx.Client | None = None) -> None:
        self._base, self._token, self._client = base_url.rstrip("/"), token, client or httpx.Client(timeout=30)

    def get_released(self, request_id: str) -> dict[str, Any] | None:
        token = self._token() if callable(self._token) else self._token
        r = self._client.get(f"{self._base}/internal/cost-writes/{request_id}", headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    def __repr__(self) -> str:
        return "HttpProcurementApi(token=***)"
