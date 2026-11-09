"""T038: the worker pass refreshes the exchange rates (about once a day) and purges old rows; a failed refresh never fails the pass."""

from __future__ import annotations

import httpx
from db.tables import fx_rates
from mmi_common.bus import InMemoryBus
from sqlalchemy import func, select
from test_fx_rates import Source, text
from worker import FileBlobs, run_once


def stored(engine):
    with engine.begin() as c:
        return c.execute(select(func.count()).select_from(fx_rates)).scalar()


def test_a_pass_with_a_rate_source_stores_the_rates_and_reports_it(engine):
    out = run_once(engine, InMemoryBus(), FileBlobs(), None, rates=Source(text()))
    assert out["fx"] == "stored" and stored(engine) == 9


def test_the_next_pass_within_the_day_does_not_call_the_service(engine):
    run_once(engine, InMemoryBus(), FileBlobs(), None, rates=Source(text()))
    second = Source(text())
    out = run_once(engine, InMemoryBus(), FileBlobs(), None, rates=second)
    assert out["fx"] == "fresh" and second.calls == 0


def test_a_failed_refresh_is_reported_but_the_pass_still_succeeds(engine):
    out = run_once(engine, InMemoryBus(), FileBlobs(), None, rates=Source(httpx.ConnectError("down")))
    assert out["fx"] == "failed" and out["failed"] == 0 and stored(engine) == 0


def test_without_a_rate_source_the_pass_is_unchanged(engine):
    out = run_once(engine, InMemoryBus(), FileBlobs(), None)
    assert "fx" not in out and stored(engine) == 0


def test_a_failure_in_the_rate_storage_step_does_not_stop_the_event_relay(engine, monkeypatch):
    """T066 (FR-043, SC-014): the relay runs in the same pass, the pass reports the error, and the next pass tries again."""
    calls = []
    monkeypatch.setattr("worker.relay_once", lambda *a, **k: calls.append(1) or 0)

    def broken(*a, **k):
        raise RuntimeError("database error while storing rates")

    monkeypatch.setattr("fx.rates.store_rates", broken)
    out = run_once(engine, InMemoryBus(), FileBlobs(), None, rates=Source(text()))
    assert calls == [1] and out["fx"] == "error" and stored(engine) == 0
    out = run_once(engine, InMemoryBus(), FileBlobs(), None, rates=Source(text()))        # the audited failure starts the one-hour backoff; the relay is unaffected
    assert calls == [1, 1] and out["fx"] == "backoff"


def test_the_storage_failure_is_audited_in_its_own_transaction(engine, monkeypatch):
    from db.tables import audit_events

    monkeypatch.setattr("fx.rates.store_rates", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    run_once(engine, InMemoryBus(), FileBlobs(), None, rates=Source(text()))
    with engine.begin() as c:
        events = [e for e in c.execute(select(audit_events)).all() if e.action == "fx.refresh_failed"]
    assert [e.after for e in events] == [{"code": "fx_storage_error"}]
