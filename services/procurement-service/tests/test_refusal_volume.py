# ruff: noqa: F811
"""T054 (FR-038, SC-013): repeated identical refusals do not grow the audit trail without limit, and nothing real is lost.

No valid sign-in: counted, never stored one by one. Same caller, target and reason inside one minute: one entry, and the next entry that is
stored carries how many repeats were skipped. A different caller, target or reason is always stored.
"""

from __future__ import annotations

import pytest
from audit.chain import verify_chain
from refusal_support import app, client, engine, h, refusals, sid  # noqa: F401
from test_terms_api import BODY

BAD = {**BODY, "delivery_charge": "-1"}


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("api.refusals._clock", lambda: now[0])
    return now


def bad(client, sid, role="buyer", extra=None):
    return client.put(f"/suppliers/{sid}/terms", json=BAD, headers=h(role, **(extra or {})))


def test_a_thousand_identical_refusals_in_a_minute_leave_one_entry(client, engine, sid, clock):
    for _ in range(1000):
        assert bad(client, sid).status_code == 422
    assert len(refusals(engine)) == 1


def test_the_next_entry_after_the_minute_carries_the_number_of_skipped_repeats(client, engine, sid, clock):
    for _ in range(30):
        bad(client, sid)
    clock[0] += 61
    bad(client, sid)
    entries = refusals(engine)
    assert [e[4] for e in entries] == [{"code": "terms_negative_amount", "status": 422}, {"code": "terms_negative_amount", "status": 422, "repeats": 29}]


def test_a_different_caller_target_or_reason_is_still_recorded(client, engine, sid, clock):
    bad(client, sid)
    bad(client, sid, "viewer")                                                                                    # other caller (403)
    client.put(f"/suppliers/{sid}/terms", json={**BODY, "lead_time_days": 9999}, headers=h())                    # other reason
    client.put("/suppliers/another/terms", json=BAD, headers=h())                                                # other target
    assert len(refusals(engine)) == 4


def test_requests_with_no_valid_sign_in_are_not_stored_one_by_one(client, engine, sid, clock):
    for _ in range(25):
        assert client.put(f"/suppliers/{sid}/terms", json=BODY).status_code == 401
    assert refusals(engine) == []


def test_the_chain_still_verifies_and_real_changes_are_still_audited(client, engine, sid, clock):
    for _ in range(5):
        bad(client, sid)
    assert client.put(f"/suppliers/{sid}/terms", json=BODY, headers=h()).status_code == 200
    with engine.begin() as c:
        assert verify_chain(c).ok


def test_skipped_repeats_are_logged_when_the_window_closes_without_a_later_identical_refusal(client, engine, sid, clock, caplog):
    """T064 (FR-038): the count is not lost when no identical refusal comes after the minute."""
    import logging

    caplog.set_level(logging.INFO, logger="procurement.refusals")
    for _ in range(8):
        bad(client, sid)
    clock[0] += 61
    client.put("/suppliers/another/terms", json=BAD, headers=h())                    # any later refusal closes the old window
    assert any("skipped 7" in r.getMessage() and "terms_negative_amount" in r.getMessage() for r in caplog.records)


def test_skipped_sign_in_failures_are_counted(client, sid, clock):
    for _ in range(12):
        client.put(f"/suppliers/{sid}/terms", json=BODY)
    assert client.app.state.refusal_unauthenticated == 12


def test_fifty_identical_refusals_at_the_same_instant_leave_one_entry_and_an_exact_count(client, engine, sid, clock, monkeypatch):
    """T065 (FR-042, SC-014): the check-then-store step cannot race, and no count is lost."""
    import time
    from concurrent.futures import ThreadPoolExecutor

    def slow_clock():                                        # widens any race window; harmless when the bookkeeping is on one thread
        time.sleep(0.002)
        return clock[0]

    monkeypatch.setattr("api.refusals._clock", slow_clock)
    with ThreadPoolExecutor(50) as pool:
        statuses = list(pool.map(lambda _: bad(client, sid).status_code, range(50)))
    assert set(statuses) == {422}
    assert len(refusals(engine)) == 1
    clock[0] += 61
    bad(client, sid)
    assert [e[4].get("repeats") for e in refusals(engine)] == [None, 49]


def test_the_bookkeeping_never_runs_on_a_worker_thread(client, engine, sid, clock, monkeypatch):
    """T071 (FR-042): fails every time if `_skip` moves back into the thread that writes to the database."""
    import threading

    from api import refusals as module

    names = []
    original = module._skip

    def spy(request, key):
        names.append(threading.current_thread().name)
        return original(request, key)

    monkeypatch.setattr(module, "_skip", spy)
    bad(client, sid)
    assert names and not any("worker" in n.lower() for n in names)


def test_a_failed_write_does_not_silence_the_next_identical_refusal(client, engine, sid, clock, monkeypatch):
    """T072 (FR-038, FR-042)."""
    from api import refusals as module

    original, calls = module._write, []

    def flaky(*args):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database briefly down")
        return original(*args)

    monkeypatch.setattr(module, "_write", flaky)
    assert bad(client, sid).status_code == 422 and refusals(engine) == []
    assert bad(client, sid).status_code == 422
    assert len(refusals(engine)) == 1


def test_the_minute_summary_reports_how_many_sign_in_failures_were_not_stored(client, engine, sid, clock, caplog):
    """T073 (FR-038)."""
    import logging

    caplog.set_level(logging.INFO, logger="procurement.refusals")
    for _ in range(5):
        client.put(f"/suppliers/{sid}/terms", json=BODY)
    clock[0] += 61
    client.put(f"/suppliers/{sid}/terms", json=BODY)                      # even another sign-in failure closes the window and reports
    assert any("5 sign-in failures" in r.getMessage() for r in caplog.records)
