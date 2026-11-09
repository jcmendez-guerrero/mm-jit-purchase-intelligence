"""T036 (FR-034, FR-036): ECB reference rates from Frankfurter are fetched at most once a day through an allowlisted request, stored with their
publication date, and read from the database only. A failure never stops the worker and never loses what is stored.

Response shape recorded 2026-11-09 from one public GET (list of {date, base, quote, rate}); the fixture uses invented round numbers.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from db.tables import fx_rates, terms_idempotency
from fx.rates import (
    ALLOWED_URL,
    FxError,
    HttpRatesSource,
    convert,
    latest_rate,
    parse_rates,
    purge,
    rate_state,
    refresh_if_due,
)
from sqlalchemy import func, insert, select

D = Decimal
FIXTURE = Path(__file__).resolve().parents[3] / "packages" / "testing" / "fixtures" / "fx" / "ecb_rates.v1.json"
NOW = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
TODAY = NOW.date()


def text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


class Source:
    """Stands in for the HTTP source: returns ``payload`` or raises it when it is an exception."""

    def __init__(self, payload):
        self.payload, self.calls = payload, 0

    def fetch(self) -> str:
        self.calls += 1
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def count(conn, table):
    return conn.execute(select(func.count()).select_from(table)).scalar()


# ---- parsing ----
def test_the_response_is_read_as_exact_decimals_and_euro_itself_is_skipped():
    rates = {r.currency: r for r in parse_rates(text())}
    assert len(rates) == 9 and "EUR" not in rates
    assert rates["USD"].eur_per_unit == D("0.8") and rates["USD"].published_on == date(2026, 11, 6)
    assert rates["IDR"].eur_per_unit == D("0.000058823529")                       # 1 / 17000, twelve decimals


@pytest.mark.parametrize("payload", [
    "not json", "{}", "[]", '[{"date": "2026-11-06", "base": "EUR", "quote": "USD"}]',
    '[{"date": "2026-11-06", "base": "USD", "quote": "GBP", "rate": 0.8}]',          # not quoted against the euro
    '[{"date": "2026-11-06", "base": "EUR", "quote": "usd", "rate": 1.25}]',
    '[{"date": "2026-11-06", "base": "EUR", "quote": "USD", "rate": 0}]',
    '[{"date": "2026-11-06", "base": "EUR", "quote": "USD", "rate": -1.2}]',
    '[{"date": "2026-11-06", "base": "EUR", "quote": "USD", "rate": "abc"}]',
    '[{"date": "06/11/2026", "base": "EUR", "quote": "USD", "rate": 1.25}]',
])
def test_a_malformed_response_is_refused_as_a_whole(payload):
    with pytest.raises(FxError) as exc:
        parse_rates(payload)
    assert exc.value.code == "fx_response_invalid"


# ---- the allowlisted request ----
def test_only_the_one_approved_url_is_accepted():
    HttpRatesSource(ALLOWED_URL)
    for bad in (
        "http://api.frankfurter.dev/v2/providers/ecb/rates?base=EUR",                 # not https
        "https://api.frankfurter.app/v2/providers/ecb/rates?base=EUR",                # another host
        "https://api.frankfurter.dev/v2/rates?base=EUR",                              # another path (the blended feed)
        "https://api.frankfurter.dev/v2/providers/ecb/rates?base=USD",                # another query
        "https://api.frankfurter.dev/v2/providers/ecb/rates?base=EUR&x=1",
        "https://user:pw@api.frankfurter.dev/v2/providers/ecb/rates?base=EUR",
        "https://api.frankfurter.dev:8443/v2/providers/ecb/rates?base=EUR",
        "https://api.frankfurter.dev/v2/providers/ecb/rates?base=EUR#x",
    ):
        with pytest.raises(FxError) as exc:
            HttpRatesSource(bad)
        assert exc.value.code == "fx_request_refused", bad


def test_the_request_is_a_plain_get_with_no_credentials_and_no_body():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=text(), headers={"content-type": "application/json"})

    body = HttpRatesSource(ALLOWED_URL, httpx.Client(transport=httpx.MockTransport(handler))).fetch()
    (req,) = seen
    assert body == text() and req.method == "GET" and (req.url.host, req.url.path, req.url.query) == ("api.frankfurter.dev", "/v2/providers/ecb/rates", b"base=EUR")
    assert not {"authorization", "cookie", "x-api-key"} & {k.lower() for k in req.headers} and req.content == b""


@pytest.mark.parametrize("response", [
    httpx.Response(503), httpx.Response(404), httpx.Response(302, headers={"location": "https://evil.example/x"}),
    httpx.Response(200, text="x" * 300_000, headers={"content-type": "application/json"}),               # far larger than a rate table
    httpx.Response(200, text="<html></html>", headers={"content-type": "text/html"}),
])
def test_an_unexpected_answer_is_refused(response):
    source = HttpRatesSource(ALLOWED_URL, httpx.Client(transport=httpx.MockTransport(lambda r: response)))
    with pytest.raises(FxError) as exc:
        source.fetch()
    assert exc.value.code in {"fx_unavailable", "fx_response_invalid"}


# ---- the daily refresh ----
def test_the_first_refresh_stores_every_currency_with_its_publication_date(conn):
    assert refresh_if_due(conn, Source(text()), NOW) == "stored"
    rows = {r.currency: r for r in conn.execute(select(fx_rates)).all()}
    assert len(rows) == 9 and rows["GBP"].published_on == date(2026, 11, 6) and rows["GBP"].provider == "ecb"
    assert rows["GBP"].eur_per_unit == D("1.25") and rows["GBP"].fetched_at.replace(tzinfo=UTC) == NOW


def test_a_second_refresh_within_twenty_hours_does_not_call_the_service(conn):
    refresh_if_due(conn, Source(text()), NOW)
    again = Source(text())
    assert refresh_if_due(conn, again, NOW + timedelta(hours=19)) == "fresh" and again.calls == 0


def test_after_twenty_hours_it_calls_again_and_never_duplicates_a_day(conn):
    refresh_if_due(conn, Source(text()), NOW)
    later = Source(text())
    assert refresh_if_due(conn, later, NOW + timedelta(hours=21)) == "stored" and later.calls == 1
    assert count(conn, fx_rates) == 9                                              # same publication date: nothing added


def test_a_new_publication_day_adds_rows_and_keeps_the_old_ones(conn):
    refresh_if_due(conn, Source(text()), NOW)
    next_day = text().replace("2026-11-06", "2026-11-09")
    refresh_if_due(conn, Source(next_day), NOW + timedelta(days=1))
    assert count(conn, fx_rates) == 18


@pytest.mark.parametrize("failure", [httpx.ConnectError("down"), httpx.ReadTimeout("slow"), FxError("fx_unavailable"), "not json"])
def test_a_failed_refresh_reports_it_keeps_what_is_stored_and_never_raises(conn, failure):
    refresh_if_due(conn, Source(text()), NOW)
    before = [tuple(r) for r in conn.execute(select(fx_rates).order_by(fx_rates.c.currency)).all()]
    assert refresh_if_due(conn, Source(failure), NOW + timedelta(days=2)) == "failed"
    assert [tuple(r) for r in conn.execute(select(fx_rates).order_by(fx_rates.c.currency)).all()] == before


def test_after_a_failure_the_service_is_left_alone_for_an_hour_and_the_failure_is_audited(conn):
    """An outage must not turn a short cron interval into a stream of requests."""
    from db.tables import audit_events

    down = Source(httpx.ConnectError("down"))
    assert refresh_if_due(conn, down, NOW) == "failed" and down.calls == 1
    assert refresh_if_due(conn, down, NOW + timedelta(minutes=30)) == "backoff" and down.calls == 1
    assert refresh_if_due(conn, down, NOW + timedelta(minutes=61)) == "failed" and down.calls == 2
    events = [e for e in conn.execute(select(audit_events)).all() if e.action == "fx.refresh_failed"]
    assert len(events) == 2 and events[0].after == {"code": "fx_unavailable"}
    healthy = Source(text())
    assert refresh_if_due(conn, healthy, NOW + timedelta(hours=3)) == "stored" and healthy.calls == 1


def test_a_failure_with_nothing_stored_leaves_the_table_empty(conn):
    assert refresh_if_due(conn, Source(httpx.ConnectError("down")), NOW) == "failed" and count(conn, fx_rates) == 0


# ---- reading rates ----
def test_the_newest_rate_published_on_or_before_today_is_used(conn):
    refresh_if_due(conn, Source(text()), NOW)
    refresh_if_due(conn, Source(text().replace("2026-11-06", "2026-11-12").replace("1.25", "9.99")), NOW + timedelta(days=1))
    assert latest_rate(conn, "USD", TODAY).published_on == date(2026, 11, 6)       # the 12th is in the future for a proposal dated the 9th
    assert latest_rate(conn, "USD", date(2026, 11, 12)).published_on == date(2026, 11, 12)
    assert latest_rate(conn, "XYZ", TODAY) is None


def test_a_rate_is_usable_for_seven_days_and_stale_after_that(conn):
    refresh_if_due(conn, Source(text()), NOW)
    rate = latest_rate(conn, "USD", TODAY)
    assert rate_state(rate, date(2026, 11, 13)) == "ok" and rate_state(rate, date(2026, 11, 13)) == "ok"
    assert rate_state(rate, date(2026, 11, 6) + timedelta(days=7)) == "ok"
    assert rate_state(rate, date(2026, 11, 6) + timedelta(days=8)) == "stale"
    assert rate_state(None, TODAY) == "missing"


def test_conversion_is_exact_decimal_rounded_half_up_to_four_places(conn):
    refresh_if_due(conn, Source(text()), NOW)
    assert convert(D("10.00"), latest_rate(conn, "USD", TODAY)) == D("8.0000")
    assert convert(D("100000"), latest_rate(conn, "IDR", TODAY)) == D("5.8824")    # 5.8823529 rounds up


# ---- housekeeping ----
def test_purge_removes_old_rates_and_old_retry_keys_only(conn):
    old, recent = NOW - timedelta(days=401), NOW - timedelta(days=399)
    for published, stamp in ((old.date(), old), (recent.date(), recent)):
        conn.execute(insert(fx_rates).values(currency="USD", published_on=published, eur_per_unit=D("0.8"), fetched_at=stamp, provider="ecb"))
    for key, stamp in (("old", NOW - timedelta(days=8)), ("new", NOW - timedelta(days=6))):
        conn.execute(insert(terms_idempotency).values(scope="supplier_terms", key=key, request_hash="h" * 64, result_version=1, actor="a", created_at=stamp))
    removed = purge(conn, NOW)
    assert removed == {"fx_rates": 1, "terms_idempotency": 1}
    assert [r.published_on for r in conn.execute(select(fx_rates)).all()] == [recent.date()]
    assert [r.key for r in conn.execute(select(terms_idempotency)).all()] == ["new"]
