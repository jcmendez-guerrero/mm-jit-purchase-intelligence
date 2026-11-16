"""T006 (FR-002, US1.1): the same inputs give the same proposal, line by line, with the same recorded input and rule versions."""

from conftest import NOW
from db.tables import proposal_lines, proposals
from proposals.generate import generate, store
from scen import base as base_inputs
from scen import suppliers
from sqlalchemy import select


def lines(conn, pid):
    return [(r.variant_id, r.supplier_id, r.qty, str(r.unit_cost_with_recargo), str(r.line_total), r.explanation)
            for r in conn.execute(select(proposal_lines).where(proposal_lines.c.proposal_id == pid).order_by(proposal_lines.c.variant_id)).all()]


def test_two_generations_are_identical_line_by_line_and_carry_the_same_versions(conn):
    sa, sb = suppliers(conn)
    a, b = generate(base_inputs(sa, sb), 10), generate(base_inputs(sa, sb), 10)
    assert a.lines == b.lines and a.inputs_hash == b.inputs_hash and a.rule_versions == b.rule_versions
    pid = store(conn, a, "buyer-1", "2026-W46", None, NOW)
    assert store(conn, b, "buyer-2", "2026-W46", None, NOW) == pid                       # the same week and inputs return the stored proposal
    p = conn.execute(select(proposals).where(proposals.c.id == pid)).one()
    assert p.inputs_hash == a.inputs_hash and p.rule_versions == a.rule_versions and lines(conn, pid)
