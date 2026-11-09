"""T009: a refused request leaves a tamper-evident audit entry with the actor, target, error code and status, and never a request body."""

from __future__ import annotations

import pytest
from audit.chain import record_refusal, verify_chain
from db.tables import audit_events
from sqlalchemy import select


def test_refusal_is_recorded_with_code_and_status_only(conn):
    record_refusal(conn, "buyer@example.test", "terms.refused", "supplier_terms", "sup-1", "revision_conflict", 412)
    row = conn.execute(select(audit_events)).one()
    assert (row.actor, row.action, row.entity, row.entity_id) == ("buyer@example.test", "terms.refused", "supplier_terms", "sup-1")
    assert row.before is None and row.after == {"code": "revision_conflict", "status": 412}


def test_refusals_extend_the_verifiable_chain(conn):
    record_refusal(conn, "a", "terms.refused", "supplier_terms", "s1", "auth_forbidden_role", 403)
    record_refusal(conn, "b", "supplier.refused", "supplier", "s2", "terms_negative_amount", 422)
    assert verify_chain(conn).ok and verify_chain(conn).checked == 2


@pytest.mark.parametrize("action", ["terms.saved", "refused", "terms.refused.extra", ""])
def test_only_refused_actions_are_accepted(conn, action):
    with pytest.raises(ValueError):
        record_refusal(conn, "a", action, "supplier_terms", "s1", "revision_conflict", 412)
    assert conn.execute(select(audit_events)).first() is None


@pytest.mark.parametrize(("code", "status"), [("Revision Conflict", 412), ("a sentence with spaces", 403), ("", 403), ("revision_conflict", 200), ("revision_conflict", 700)])
def test_code_must_be_snake_case_and_status_an_error(conn, code, status):
    with pytest.raises(ValueError):
        record_refusal(conn, "a", "terms.refused", "supplier_terms", "s1", code, status)
    assert conn.execute(select(audit_events)).first() is None
