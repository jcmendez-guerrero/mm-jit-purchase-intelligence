"""T020 (FR-010, spec Q4): buyers, approvers and admins may export an approved proposal; a viewer is refused and the refusal is audited."""

from __future__ import annotations

import pytest
from db.tables import audit_events
from proposal_support import approve_flow, generate, h
from sqlalchemy import select


@pytest.mark.parametrize("role", ["buyer", "approver", "admin"])
@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_permitted_roles_export_an_approved_proposal(api, role, fmt):
    c, _ = api
    pid = generate(c)
    approve_flow(c, pid)
    assert c.get(f"/proposals/{pid}/export?format={fmt}", headers=h(role)).status_code == 200


def test_a_viewer_is_refused_and_the_refusal_is_audited(api, engine):
    c, _ = api
    pid = generate(c)
    approve_flow(c, pid)
    r = c.get(f"/proposals/{pid}/export?format=csv", headers=h("viewer"))
    assert r.status_code == 403 and r.json()["detail"] == "auth_forbidden_role"
    with engine.connect() as conn:
        rows = conn.execute(select(audit_events).where(audit_events.c.action == "proposal.refused")).all()
    assert len(rows) == 1 and rows[0].actor == "user-viewer" and rows[0].entity_id == pid and rows[0].after == {"code": "auth_forbidden_role", "status": 403}


def test_a_refused_export_leaves_the_proposal_unexported(api):
    c, _ = api
    pid = generate(c)
    approve_flow(c, pid)
    c.get(f"/proposals/{pid}/export?format=csv", headers=h("viewer"))
    assert c.get(f"/proposals/{pid}", headers=h("viewer")).json()["status"] == "approved"


def test_an_unapproved_proposal_is_not_exported_even_for_a_permitted_role(api):
    c, _ = api
    pid = generate(c)
    assert c.get(f"/proposals/{pid}/export?format=csv", headers=h("buyer")).status_code == 409


def test_a_very_long_id_is_cut_to_the_audit_column_width_and_still_answers_403(api, engine):
    """T054: the audit entity id is 60 characters wide on PostgreSQL; a longer one must not turn the refusal into a server error."""
    c, _ = api
    long_id = "x" * 200
    assert c.get(f"/proposals/{long_id}/export?format=csv", headers=h("viewer")).status_code == 403
    with engine.connect() as conn:
        assert [len(r.entity_id) for r in conn.execute(select(audit_events).where(audit_events.c.action == "proposal.refused")).all()] == [60]
