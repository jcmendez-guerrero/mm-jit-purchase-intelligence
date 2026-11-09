"""MMI-6 (FR-034 to FR-036): EUR reference rates for suppliers that quote in another currency.

The only outbound request of this module is one GET of the ECB provider rates from Frankfurter (https://frankfurter.dev): fixed host, fixed
path, fixed query, no credentials and no data sent. It runs inside the procurement worker at most about once a day. Rates are stored with
their publication date and read from the database only: proposal generation never calls the service. A rate older than 7 days is stale;
a missing or stale rate leaves the supplier out of automatic allocation (see proposals/inputs.py). The data is provided as is and is used
for comparison and allocation, not accounting.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from audit.chain import append as audit
from db.tables import audit_events, fx_rates
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Connection
from terms.idempotency import forget_older_than

__all__ = ["ALLOWED_URL", "MAX_AGE_DAYS", "FxError", "HttpRatesSource", "Rate", "RatesSource", "convert", "latest_rate", "parse_rates", "purge", "rate_state", "refresh_if_due"]

log = logging.getLogger("procurement.fx")

ALLOWED_URL = "https://api.frankfurter.dev/v2/providers/ecb/rates?base=EUR"
PROVIDER = "ecb"
REFRESH_AFTER = timedelta(hours=20)          # a pass fetches only when the newest confirmation is older than this
RETRY_AFTER = timedelta(hours=1)             # after a failure the service is left alone for this long
MAX_AGE_DAYS = 7                             # a rate published more than this many days before the proposal date is stale
RATE_RETENTION = timedelta(days=400)
MAX_BODY_BYTES = 200_000                     # the real answer is about 2 KB
TIMEOUT_S = 10.0
_QUANT = Decimal("1e-12")
_CURRENCY = re.compile(r"[A-Z]{3}")


class FxError(Exception):
    """A refusal or failure with a stable code: fx_request_refused, fx_unavailable or fx_response_invalid."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Rate:
    currency: str
    eur_per_unit: Decimal                    # EUR for one unit of ``currency``
    published_on: date


class RatesSource(Protocol):
    def fetch(self) -> str:
        """The raw JSON text of the rates answer."""


def _check_url(url: str) -> None:
    parts = urlsplit(url)
    allowed = urlsplit(ALLOWED_URL)
    same = (parts.scheme, parts.hostname, parts.port, parts.username, parts.password, parts.path, parts.query, parts.fragment) == (
        allowed.scheme, allowed.hostname, None, None, None, allowed.path, allowed.query, "")
    if not same:
        raise FxError("fx_request_refused")


class HttpRatesSource:
    """GET of the one approved URL. Anything else is refused before a request is built (constitution: host, path and method allowlist)."""

    def __init__(self, url: str = ALLOWED_URL, client: httpx.Client | None = None) -> None:
        _check_url(url)
        self.url, self.client = url, client

    def fetch(self) -> str:
        client = self.client or httpx.Client(timeout=TIMEOUT_S, follow_redirects=False)
        try:
            res = client.get(self.url, headers={"Accept": "application/json"})
        except httpx.HTTPError as exc:
            raise FxError("fx_unavailable") from exc
        if res.status_code != 200:
            raise FxError("fx_unavailable")
        if "json" not in res.headers.get("content-type", "") or len(res.content) > MAX_BODY_BYTES:
            raise FxError("fx_response_invalid")
        return res.text


def parse_rates(text: str) -> list[Rate]:
    """The answer is a list of {date, base, quote, rate}; numbers are read as exact decimals. A malformed row refuses the whole answer."""
    try:
        data = json.loads(text, parse_float=Decimal, parse_int=Decimal)
    except ValueError as exc:
        raise FxError("fx_response_invalid") from exc
    if not isinstance(data, list) or not data:
        raise FxError("fx_response_invalid")
    out: dict[tuple[str, date], Rate] = {}
    for row in data:
        try:
            quote, base, rate, day = row["quote"], row["base"], row["rate"], date.fromisoformat(row["date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise FxError("fx_response_invalid") from exc
        if base != "EUR" or not isinstance(quote, str) or not _CURRENCY.fullmatch(quote) or not isinstance(rate, Decimal) or not rate.is_finite() or rate <= 0:
            raise FxError("fx_response_invalid")
        if quote != "EUR":
            out[(quote, day)] = Rate(quote, (Decimal(1) / rate).quantize(_QUANT, rounding=ROUND_HALF_UP), day)
    return list(out.values())


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def store_rates(conn: Connection, rates: list[Rate], fetched_at: datetime) -> None:
    """New (currency, day) pairs are added; pairs already stored are confirmed (``fetched_at`` moves), so a quiet weekend does not re-trigger the fetch."""
    known = {(r.currency, r.published_on) for r in conn.execute(select(fx_rates.c.currency, fx_rates.c.published_on)).all()}
    for r in rates:
        if (r.currency, r.published_on) in known:
            conn.execute(update(fx_rates).where(fx_rates.c.currency == r.currency, fx_rates.c.published_on == r.published_on).values(fetched_at=fetched_at))
        else:
            conn.execute(insert(fx_rates).values(currency=r.currency, published_on=r.published_on, eur_per_unit=r.eur_per_unit, fetched_at=fetched_at, provider=PROVIDER))


def refresh_if_due(conn: Connection, source: RatesSource, now: datetime) -> str:
    """One worker pass: ``fresh`` (nothing to do), ``backoff`` (a recent failure), ``stored`` or ``failed``. Never raises: the worker has other work."""
    newest = conn.execute(select(func.max(fx_rates.c.fetched_at))).scalar()
    if newest is not None and now - _aware(newest) < REFRESH_AFTER:
        return "fresh"
    last_failure = conn.execute(select(func.max(audit_events.c.ts)).where(audit_events.c.action == "fx.refresh_failed")).scalar()
    if last_failure is not None and now - _aware(last_failure) < RETRY_AFTER:
        return "backoff"
    try:
        rates = parse_rates(source.fetch())
    except (FxError, httpx.HTTPError, ValueError) as exc:
        code = exc.code if isinstance(exc, FxError) else "fx_unavailable"
        log.warning("exchange-rate refresh failed: %s", code)
        audit(conn, "svc-procurement", "fx.refresh_failed", "fx_rates", PROVIDER, after={"code": code}, now=now)
        return "failed"
    store_rates(conn, rates, now)
    return "stored"


def latest_rate(conn: Connection, currency: str, today: date) -> Rate | None:
    """The newest rate published on or before ``today`` (a rate dated in the future is not known yet for that proposal)."""
    row = conn.execute(select(fx_rates).where(fx_rates.c.currency == currency, fx_rates.c.published_on <= today)
                       .order_by(fx_rates.c.published_on.desc()).limit(1)).first()
    return None if row is None else Rate(currency, Decimal(str(row.eur_per_unit)), row.published_on)


def rate_state(rate: Rate | None, today: date) -> str:
    """``ok``, ``stale`` (older than 7 days) or ``missing`` (no rate for the currency)."""
    if rate is None:
        return "missing"
    return "stale" if (today - rate.published_on).days > MAX_AGE_DAYS else "ok"


def convert(amount: Decimal, rate: Rate) -> Decimal:
    return (amount * rate.eur_per_unit).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def purge(conn: Connection, now: datetime) -> dict[str, int]:
    """Housekeeping for the worker: old rates and expired retry keys (nothing else in this service is purged)."""
    old = conn.execute(delete(fx_rates).where(fx_rates.c.published_on < (now - RATE_RETENTION).date()))
    return {"fx_rates": int(old.rowcount or 0), "terms_idempotency": forget_older_than(conn, now)}
