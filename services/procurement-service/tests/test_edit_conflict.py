"""T008 (FR-005, spec Q3): a save based on a stale version is rejected with proposal_line_conflict, changes nothing and is audited."""

from __future__ import annotations

from db.tables import audit_events
from proposal_support import generate, h
from sqlalchemy import select


def test_a_stale_line_save_is_rejected_unchanged_and_audited(api, engine):
    c, _ = api
    pid = generate(c)
    line = c.get(f"/proposals/{pid}", headers=h("viewer")).json()["lines"][0]
    assert c.patch(f"/proposals/{pid}/lines/{line['id']}", json={"qty": line["qty"] + 6}, headers=h("buyer2", **{"If-Match": "1"})).status_code == 200
    stale = c.patch(f"/proposals/{pid}/lines/{line['id']}", json={"qty": 12}, headers=h("buyer", **{"If-Match": "1"}))
    assert stale.status_code == 409 and stale.json()["detail"] == "proposal_line_conflict"
    after = c.get(f"/proposals/{pid}", headers=h("viewer")).json()
    assert after["version"] == 2 and after["lines"][0]["qty"] == line["qty"] + 6 and after["last_edited_by"] == "user-buyer2"
    with engine.connect() as conn:
        rows = conn.execute(select(audit_events).where(audit_events.c.action == "proposal.refused")).all()
    assert len(rows) == 1 and rows[0].actor == "user-buyer" and rows[0].after == {"code": "proposal_line_conflict", "status": 409}


def test_other_conflicts_keep_their_existing_code(api):
    c, _ = api
    pid = generate(c)
    assert c.post(f"/proposals/{pid}/submit", headers=h("buyer", **{"If-Match": "9"})).json()["detail"] == "version_conflict"
