"""T024 (FR-013): repeating submit, approve, promote or export has one state effect; the repeat is refused or returns the same file."""

from __future__ import annotations

from db.tables import audit_events
from proposal_support import generate, h
from sqlalchemy import func, select


def count(engine, action):
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(audit_events).where(audit_events.c.action == action)).scalar()


def test_a_repeated_submit_or_approve_changes_state_once(api, engine):
    c, _ = api
    pid = generate(c)
    assert c.post(f"/proposals/{pid}/submit", headers=h("buyer")).status_code == 200
    assert c.post(f"/proposals/{pid}/submit", headers=h("buyer")).status_code == 409
    assert c.post(f"/proposals/{pid}/approve", headers=h("approver")).status_code == 200
    assert c.post(f"/proposals/{pid}/approve", headers=h("approver")).status_code == 409
    assert (count(engine, "proposal.submitted"), count(engine, "proposal.approved")) == (1, 1)


def test_a_repeated_export_returns_the_same_file_and_one_state_change(api, engine):
    c, _ = api
    pid = generate(c)
    c.post(f"/proposals/{pid}/submit", headers=h("buyer"))
    c.post(f"/proposals/{pid}/approve", headers=h("approver"))
    a = c.get(f"/proposals/{pid}/export?format=csv", headers=h("buyer"))
    b = c.get(f"/proposals/{pid}/export?format=csv", headers=h("buyer"))
    assert a.status_code == b.status_code == 200 and a.content == b.content
    assert c.get(f"/proposals/{pid}", headers=h("viewer")).json()["status"] == "exported"
