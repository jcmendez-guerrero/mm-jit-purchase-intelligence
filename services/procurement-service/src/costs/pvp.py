"""Selling price (PVP) lookup for the margin check (FR-043).

The product-level ERP cost applies to every variant of the product, so the margin is judged against the LOWEST variant PVP (the
tightest margin). A variant without a price is skipped; no price at all means the margin is reported as unavailable.
ASSUMPTION (T066): the price comes from the newest priced ERP stock movement; the owner still has to confirm source, freshness and VAT.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any, Protocol

import httpx

from costs.lot_lookup import LotLookupError


class PvpSource(Protocol):
    def prices(self, variant_ids: Sequence[int]) -> dict[int, Decimal]: ...


class HttpPvpSource:
    def __init__(self, base_url: str, token: str | Callable[[], str], client: httpx.Client | None = None) -> None:
        self._base, self._token, self._client = base_url.rstrip("/"), token, client or httpx.Client(timeout=15)

    def prices(self, variant_ids: Sequence[int]) -> dict[int, Decimal]:
        token = self._token() if callable(self._token) else self._token
        r = self._client.get(f"{self._base}/pvp", params={"variant_ids": ",".join(str(i) for i in variant_ids)}, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return {int(p["variant_id"]): Decimal(str(p["pvp"])) for p in r.json()["prices"]}

    def __repr__(self) -> str:
        return "HttpPvpSource(token=***)"


def lowest_pvp(source: PvpSource, variant_ids: Sequence[int]) -> Decimal | None:
    try:
        found: dict[int, Any] = source.prices(variant_ids)
    except Exception as exc:
        raise LotLookupError("pvp_unavailable") from exc
    usable = [Decimal(str(v)) for v in found.values() if Decimal(str(v)) > 0]
    return min(usable) if usable else None
