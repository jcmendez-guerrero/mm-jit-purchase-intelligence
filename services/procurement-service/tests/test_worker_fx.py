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
