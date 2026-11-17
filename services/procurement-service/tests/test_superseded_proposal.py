"""T016/T017 (FR-008): a superseded proposal cannot be edited, submitted, approved or exported (proposal_superseded)."""

from __future__ import annotations

from db.tables import proposals
from proposal_support import approve_flow, generate, h
from sqlalchemy import update


def _supersede(engine, pid):
    with engine.begin() as conn:
        conn.execute(update(proposals).where(proposals.c.id == pid).values(status="superseded"))


def test_a_superseded_draft_cannot_be_edited_or_submitted(api, engine):
    c, _ = api
    pid = generate(c)
    line = c.get(f"/proposals/{pid}", headers=h("viewer")).json()["lines"][0]
    _supersede(engine, pid)
    for r in (c.patch(f"/proposals/{pid}/lines/{line['id']}", json={"qty": 12}, headers=h("buyer")), c.post(f"/proposals/{pid}/submit", headers=h("buyer"))):
        assert r.status_code == 409 and r.json()["detail"] == "proposal_superseded"


def test_a_superseded_proposal_cannot_be_approved_or_exported(api, engine):
    c, _ = api
    pid = generate(c)
    approve_flow(c, pid)
    _supersede(engine, pid)
    assert c.post(f"/proposals/{pid}/approve", headers=h("approver")).json()["detail"] == "proposal_superseded"
    r = c.get(f"/proposals/{pid}/export?format=csv", headers=h("buyer"))
    assert r.status_code == 409 and r.json()["detail"] == "proposal_superseded"
    assert c.get(f"/proposals/{pid}", headers=h("viewer")).json()["status"] == "superseded"
