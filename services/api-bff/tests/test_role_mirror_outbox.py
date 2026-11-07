"""T027: a role change, its audit event and its mirror-outbox row are one transaction; the relay retries visibly and never loses a change."""

from datetime import UTC, datetime, timedelta

import pytest
from db import roles as roles_module
from worker import drain_once

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


class FakeProcurement:
    def __init__(self, fail: int = 0):
        self.calls: list[tuple[str, list[str], bool, int]] = []
        self.fail = fail

    def put_user_roles(self, user_id, roles, active, revision):
        if self.fail:
            self.fail -= 1
            raise ConnectionError("procurement unavailable")
        self.calls.append((user_id, list(roles), active, revision))


def test_a_failure_while_auditing_rolls_back_the_role_and_the_outbox(role_store, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(roles_module, "append_audit", boom)
    before_roles = role_store.get("buyer-1")
    with pytest.raises(RuntimeError):
        role_store.set_roles("buyer-1", ["viewer", "buyer", "admin"], actor="admin-1")
    assert role_store.get("buyer-1") == before_roles
    assert role_store.mirror_status(NOW)["pending"] == 0


def test_a_change_queues_exactly_one_mirror_row(role_store):
    role_store.set_roles("buyer-1", ["viewer", "buyer", "approver"], actor="admin-1", now=NOW)
    assert role_store.mirror_status(NOW)["pending"] == 1


def test_the_relay_sends_the_latest_roles_with_their_revision(role_store):
    role_store.set_roles("buyer-1", ["viewer", "buyer", "approver"], actor="admin-1", now=NOW)
    role_store.set_roles("buyer-1", ["viewer", "buyer"], actor="admin-1", now=NOW)
    client = FakeProcurement()
    stats = drain_once(role_store, client, now=NOW)
    assert stats["sent"] == 2
    assert client.calls[-1] == ("buyer-1", ["buyer", "viewer"], True, 3)      # the seeded user was revision 1; two changes follow
    assert [c[3] for c in client.calls] == sorted(c[3] for c in client.calls)      # revisions never go backwards
    assert role_store.mirror_status(NOW)["pending"] == 0


def test_a_failed_call_is_retried_later_with_backoff_and_stays_visible(role_store):
    role_store.set_roles("buyer-1", ["viewer", "buyer", "approver"], actor="admin-1", now=NOW)
    client = FakeProcurement(fail=1)
    first = drain_once(role_store, client, now=NOW)
    assert first["failed_attempts"] == 1 and first["sent"] == 0
    status = role_store.mirror_status(NOW)
    assert status["pending"] == 1 and status["items"][0]["last_error_key"] == "role_mirror_failed" and status["items"][0]["attempts"] == 1
    assert drain_once(role_store, client, now=NOW + timedelta(seconds=1))["considered"] == 0        # not due yet (backoff)
    later = drain_once(role_store, client, now=NOW + timedelta(minutes=5))
    assert later["sent"] == 1 and role_store.mirror_status(NOW + timedelta(minutes=5))["pending"] == 0


def test_after_too_many_attempts_the_row_is_marked_failed_and_can_be_requeued(role_store):
    role_store.set_roles("buyer-1", ["viewer", "buyer", "approver"], actor="admin-1", now=NOW)
    client = FakeProcurement(fail=99)
    t = NOW
    for _ in range(10):
        drain_once(role_store, client, now=t, max_attempts=3)
        t += timedelta(hours=2)
    status = role_store.mirror_status(t)
    assert status["failed"] == 1 and status["pending"] == 0
    assert role_store.requeue_failed(now=t) == 1
    client.fail = 0
    assert drain_once(role_store, client, now=t)["sent"] == 1


def test_status_reports_the_age_of_the_oldest_pending_change(role_store):
    role_store.set_roles("buyer-1", ["viewer", "buyer", "approver"], actor="admin-1", now=NOW)
    assert role_store.mirror_status(NOW + timedelta(minutes=10))["oldest_pending_seconds"] == 600
