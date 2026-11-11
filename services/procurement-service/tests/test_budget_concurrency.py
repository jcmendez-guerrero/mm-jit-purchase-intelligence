"""Feature 011 (T058): two saves that both read the same revision, so the second only fails at the database, still get the conflict answer, never a server error."""

from datetime import date
from decimal import Decimal

import pytest
from db.tables import budget_caps, policy_sets
from policies import service
from policies.service import PolicyConflict, PolicyValues, clear_policy, save_budget_cap, save_policy
from sqlalchemy import func, select

TODAY = date(2026, 11, 9)


def stale_reads(monkeypatch, name, first):
    """The loser of a race read the revision before the winner committed: its first read says `first`, later reads see the truth."""
    real, calls = getattr(service, name), {"n": 0}

    def fake(*a, **k):
        calls["n"] += 1
        return first if calls["n"] == 1 else real(*a, **k)

    monkeypatch.setattr(service, name, fake)


def count(conn, table):
    return conn.execute(select(func.count()).select_from(table)).scalar()


def test_a_policy_save_that_loses_the_race_is_a_conflict_and_stores_nothing(conn, monkeypatch):
    save_policy(conn, "global", "*", PolicyValues(min_units=1), "a", today=TODAY)
    stale_reads(monkeypatch, "_current_revision", 0)
    with pytest.raises(PolicyConflict) as e:
        save_policy(conn, "global", "*", PolicyValues(min_units=2), "b", expected_revision=0, today=TODAY)
    assert e.value.current_revision == 1 and count(conn, policy_sets) == 1


def test_a_budget_cap_save_that_loses_the_race_is_a_conflict_and_stores_nothing(conn, monkeypatch):
    save_budget_cap(conn, "week", "global", None, Decimal("100"), "a", today=TODAY, expected_revision=0)
    stale_reads(monkeypatch, "budget_cap_revision", 0)
    with pytest.raises(PolicyConflict) as e:
        save_budget_cap(conn, "week", "global", None, Decimal("200"), "b", today=TODAY, expected_revision=0)
    assert e.value.current_revision == 1 and count(conn, budget_caps) == 1


def test_clearing_that_loses_the_race_is_a_conflict(conn, monkeypatch):
    save_policy(conn, "global", "*", PolicyValues(min_units=1), "a", today=TODAY)
    clear_policy(conn, "global", "*", "a", expected_revision=1, today=TODAY)
    stale_reads(monkeypatch, "_current_revision", 1)
    with pytest.raises(PolicyConflict) as e:
        clear_policy(conn, "global", "*", "b", expected_revision=1, today=TODAY)
    assert e.value.current_revision == 2 and count(conn, policy_sets) == 2
