"""Selling price (PVP) lookup for the margin check (FR-043).

The product-level ERP cost applies to every variant of the product, so the margin is judged against the LOWEST variant PVP (the
tightest margin). A variant without a price is skipped; no price at all means the margin is reported as unavailable.
ASSUMPTION (T066): the price comes from the newest priced ERP stock movement; the owner still has to confirm source, freshness and VAT.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx

from costs.lot_lookup import LotLookupError


class PvpSource(Protocol):
    def prices(self, variant_ids: Sequence[int]) -> dict[int, Decimal]: ...


@dataclass(frozen=True)
class PvpQuote:
    """A selling price with the age of its last sync confirmation. Stale means confirmed more than 7 days ago (decided by inventory)."""

    price: Decimal
    age_days: int | None
    stale: bool


@dataclass(frozen=True)
class PvpInfo:
    price: Decimal | None
    age_days: int | None = None
    stale_only: bool = False         # prices exist but every one is stale: the margin is unavailable for that reason


class HttpPvpSource:
    def __init__(self, base_url: str, token: str | Callable[[], str], client: httpx.Client | None = None) -> None:
        self._base, self._token, self._client = base_url.rstrip("/"), token, client or httpx.Client(timeout=15)

    def quotes(self, variant_ids: Sequence[int]) -> dict[int, PvpQuote]:
        token = self._token() if callable(self._token) else self._token
        r = self._client.get(f"{self._base}/pvp", params={"variant_ids": ",".join(str(i) for i in variant_ids)}, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return {int(p["variant_id"]): PvpQuote(Decimal(str(p["pvp"])), p.get("age_days"), bool(p.get("stale", False))) for p in r.json()["prices"]}

    def prices(self, variant_ids: Sequence[int]) -> dict[int, Decimal]:
        return {i: q.price for i, q in self.quotes(variant_ids).items() if not q.stale}

    def __repr__(self) -> str:
        return "HttpPvpSource(token=***)"


def lowest_pvp(source: PvpSource, variant_ids: Sequence[int]) -> Decimal | None:
    try:
        found: dict[int, Any] = source.prices(variant_ids)
    except Exception as exc:
        raise LotLookupError("pvp_unavailable") from exc
    usable = [Decimal(str(v)) for v in found.values() if Decimal(str(v)) > 0]
    return min(usable) if usable else None


def lowest_pvp_info(source: Any, variant_ids: Sequence[int]) -> PvpInfo:
    """The lowest FRESH price with its age. Stale prices count as missing; if only stale ones exist the result says so.
    A source that does not report age (older fakes) is used as before."""
    if not hasattr(source, "quotes"):
        return PvpInfo(lowest_pvp(source, variant_ids))
    try:
        found: dict[int, PvpQuote] = source.quotes(variant_ids)
    except Exception as exc:
        raise LotLookupError("pvp_unavailable") from exc
    usable = [q for q in found.values() if q.price > 0]
    fresh = [q for q in usable if not q.stale]
    if fresh:
        best = min(fresh, key=lambda q: q.price)
        return PvpInfo(best.price, best.age_days)
    if usable:
        ages = [q.age_days for q in usable if q.age_days is not None]
        return PvpInfo(None, min(ages) if ages else None, True)
    return PvpInfo(None)
