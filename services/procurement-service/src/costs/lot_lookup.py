"""T059: lots in stock, fetched from inventory when a cost-update request is built (decided 2026-11-05: no duplicated stock table).

Failure is visible: after a bounded number of attempts the caller gets ``LotLookupError('inventory_unavailable')`` and no request is
built, so a stale quantity is never used.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any, Protocol

import httpx


class LotLookupError(Exception):
    def __init__(self, code: str = "inventory_unavailable") -> None:
        super().__init__(code)
        self.code = code


class LotsSource(Protocol):
    def in_stock(self, variant_ids: Sequence[int]) -> list[dict[str, Any]]:
        """Items: {"variant_id": int, "lot": str | None, "quantity": int}."""
        ...


def fetch_lots(source: LotsSource, variant_ids: Sequence[int], attempts: int = 3, sleep: Callable[[float], None] = time.sleep, base_delay: float = 0.2) -> list[dict[str, Any]]:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return source.in_stock(variant_ids)
        except Exception as exc:
            last = exc
            if i < attempts - 1:
                sleep(base_delay * (2 ** i))
    raise LotLookupError() from last


class HttpLotsSource:
    """Calls inventory-service with an audience-scoped service token (the same pattern as the receipt poller)."""

    def __init__(self, base_url: str, token: str | Callable[[], str], client: httpx.Client | None = None) -> None:
        self._base, self._token, self._client = base_url.rstrip("/"), token, client or httpx.Client(timeout=15)

    def in_stock(self, variant_ids: Sequence[int]) -> list[dict[str, Any]]:
        token = self._token() if callable(self._token) else self._token
        r = self._client.get(f"{self._base}/lots/in-stock", params={"variant_ids": ",".join(str(i) for i in variant_ids)}, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()["lots"]  # type: ignore[no-any-return]

    def __repr__(self) -> str:
        return "HttpLotsSource(token=***)"
