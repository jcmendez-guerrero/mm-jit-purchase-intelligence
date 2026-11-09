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
