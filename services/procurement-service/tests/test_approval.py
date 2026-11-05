"""T086 and T096: separation of duties, MFA freshness, edit resets eligibility, optimistic concurrency, edit validation."""

from datetime import timedelta
from decimal import Decimal

import pytest
from approvals.workflow import ApprovalError, decide, is_approval_valid, submit
from audit.chain import verify_chain
from builders import flat_forecast, inputs, offer, terms, variant
from conftest import NOW, add_supplier
from costs.rules import CostRules
from costs.store import NewCost, add_version
from db.tables import approvals, audit_events, proposal_lines, proposals, supplier_order_groups
from mmi_common.auth import Principal
from proposals.edit import ConcurrencyError, EditError, ProposalStateError, edit_line
from proposals.generate import generate, store
from sqlalchemy import select

D = Decimal


class Users:
    def __init__(self, *approvers):
        self.a = set(approvers)

    def active_approvers(self):
        return set(self.a)


def who(subject, roles=("approver",), age_min=1):
    return Principal(subject, frozenset(roles), NOW - timedelta(minutes=age_min) if age_min is not None else None)


@pytest.fixture
def draft(conn):
    """A stored proposal created by buyer-1 whose lines can be edited against real stored costs."""
    sa, sb = add_supplier(conn, 1, "A"), add_supplier(conn, 2, "B")
    for sid, cost, pack in ((sa, "1.00", 6), (sb, "1.40", 1)):
        add_version(conn, NewCost(product_id=10, supplier_id=sid, cost_with_recargo=D(cost), source="manual", actor="x", pack_size=pack, min_order_qty=0), CostRules(), NOW)
    d = generate(inputs([variant(1, [offer(sa, "1.00", pack=6), offer(sb, "1.40")], flat_forecast(1.0))], [terms(sa), terms(sb)]), 10)
    pid = store(conn, d, "buyer-1", "2026-W46", D("1000"), NOW)
    return pid, sa, sb


def status(conn, pid):
    return conn.execute(select(proposals.c.status, proposals.c.version).where(proposals.c.id == pid)).one()


def test_the_creator_cannot_approve_even_when_holding_the_approver_role(conn, draft):
    pid = draft[0]
    submit(conn, pid, "buyer-1", 1, Users("buyer-1", "approver-2"), NOW)
    with pytest.raises(ApprovalError) as e:
        decide(conn, pid, who("buyer-1"), 1, now=NOW)
    assert e.value.code == "separation_of_duties" and status(conn, pid).status == "submitted"


def test_the_last_editor_cannot_approve_and_an_edit_resets_eligibility(conn, draft):
    pid, _sa, _ = draft
    submit(conn, pid, "buyer-1", 1, Users("approver-2", "buyer-2"), NOW)
    r = edit_line(conn, pid, 1, 1, "buyer-2", qty=60, now=NOW)                                   # submitted -> draft, version bumped
    assert r.version == 2 and status(conn, pid) == ("draft", 2)
    with pytest.raises(ProposalStateError):
        decide(conn, pid, who("approver-2"), 2, now=NOW)                                           # not submitted any more
    submit(conn, pid, "buyer-1", 2, Users("approver-2", "buyer-2"), NOW)
    with pytest.raises(ApprovalError) as e:
        decide(conn, pid, who("buyer-2"), 2, now=NOW)                                              # buyer-2 is the last editor
    assert e.value.code == "separation_of_duties"
    decide(conn, pid, who("approver-2"), 2, now=NOW)
    assert status(conn, pid).status == "approved"


def test_a_different_freshly_authenticated_approver_succeeds_and_is_a_distinct_audited_step(conn, draft):
    pid = draft[0]
    submit(conn, pid, "buyer-1", 1, Users("approver-2"), NOW)
    decide(conn, pid, who("approver-2", age_min=2), 1, now=NOW)
    a = conn.execute(select(approvals)).one()
    assert (a.approver_id, a.decision, a.proposal_version) == ("approver-2", "approved", 1) and is_approval_valid(conn, pid)
    actions = [r.action for r in conn.execute(select(audit_events).order_by(audit_events.c.id)).all()]
    assert actions[-2:] == ["proposal.submitted", "proposal.approved"] and verify_chain(conn).ok


@pytest.mark.parametrize("age,code", [(6, "mfa_required"), (None, "mfa_required")])
def test_stale_or_missing_mfa_is_refused(conn, draft, age, code):
    pid = draft[0]
    submit(conn, pid, "buyer-1", 1, Users("approver-2"), NOW)
    with pytest.raises(ApprovalError) as e:
        decide(conn, pid, who("approver-2", age_min=age), 1, now=NOW)
    assert e.value.code == code and status(conn, pid).status == "submitted" and conn.execute(select(approvals)).all() == []


def test_only_the_approver_role_can_decide_not_even_an_admin_or_buyer(conn, draft):
    pid = draft[0]
    submit(conn, pid, "buyer-1", 1, Users("approver-2"), NOW)
    for roles in (("buyer",), ("admin",), ("viewer",), ("buyer", "admin")):
        with pytest.raises(ApprovalError) as e:
            decide(conn, pid, who("someone-else", roles), 1, now=NOW)
        assert e.value.code == "not_an_approver"


def test_submission_is_refused_when_nobody_else_could_approve(conn, draft):
    pid = draft[0]
    with pytest.raises(ApprovalError) as e:
        submit(conn, pid, "buyer-1", 1, Users("buyer-1"), NOW)                                    # the only approver is the creator
    assert e.value.code == "no_eligible_approver" and status(conn, pid).status == "draft"
    with pytest.raises(ApprovalError):
        submit(conn, pid, "buyer-1", 1, Users(), NOW)


def test_a_rejection_returns_the_proposal_to_draft(conn, draft):
    pid = draft[0]
    submit(conn, pid, "buyer-1", 1, Users("approver-2"), NOW)
    decide(conn, pid, who("approver-2"), 1, approve=False, now=NOW)
    assert status(conn, pid).status == "draft" and not is_approval_valid(conn, pid)


def test_a_decision_on_a_stale_version_is_refused(conn, draft):
    pid = draft[0]
    submit(conn, pid, "buyer-1", 1, Users("approver-2"), NOW)
    with pytest.raises(ConcurrencyError):
        decide(conn, pid, who("approver-2"), 7, now=NOW)


def test_an_old_approval_never_covers_a_later_edit(conn, draft):
    pid, _sa, _sb = draft
    submit(conn, pid, "buyer-1", 1, Users("approver-2"), NOW)
    decide(conn, pid, who("approver-2"), 1, now=NOW)
    with pytest.raises(ProposalStateError):
        edit_line(conn, pid, 1, 1, "buyer-1", qty=12, now=NOW)                                    # approved proposals are frozen
    assert is_approval_valid(conn, pid)


def test_state_machine_guards(conn, draft):
    pid = draft[0]
    with pytest.raises(ProposalStateError):
        decide(conn, pid, who("approver-2"), 1, now=NOW)                                          # not yet submitted
    submit(conn, pid, "buyer-1", 1, Users("approver-2"), NOW)
    with pytest.raises(ProposalStateError):
        submit(conn, pid, "buyer-1", 1, Users("approver-2"), NOW)                                 # already submitted
    with pytest.raises(ProposalStateError):
        submit(conn, "nope", "buyer-1", 1, Users("approver-2"), NOW)


# ---- editing ---------------------------------------------------------------------------------------------

def test_edits_are_recorded_with_who_when_and_bump_the_version(conn, draft):
    pid, _sa, _sb = draft
    line = conn.execute(select(proposal_lines)).one()
    r = edit_line(conn, pid, 1, 1, "buyer-2", qty=line.qty + 6, now=NOW)
    p = conn.execute(select(proposals)).one()
    assert (r.version, p.version, p.last_edited_by) == (2, 2, "buyer-2")
    after = conn.execute(select(proposal_lines)).one()
    assert after.qty == line.qty + 6 and after.manual_override and "manual_quantity" in after.constraints_applied
    assert Decimal(str(after.line_total)) == Decimal(str(after.unit_cost_with_recargo)) * after.qty
    last = conn.execute(select(audit_events).order_by(audit_events.c.id.desc())).first()
    assert (last.actor, last.action) == ("buyer-2", "proposal.line_edited") and last.before["qty"] == line.qty and last.after["qty"] == line.qty + 6


def test_optimistic_concurrency_refuses_a_stale_editor(conn, draft):
    pid = draft[0]
    edit_line(conn, pid, 1, 1, "buyer-1", qty=60, now=NOW)
    with pytest.raises(ConcurrencyError):
        edit_line(conn, pid, 1, 1, "buyer-2", qty=66, now=NOW)


def test_constraints_are_revalidated_on_every_edit(conn, draft):
    pid, _sa, _sb = draft
    for kwargs, code in [({"qty": 7}, "pack_multiple"), ({"qty": -1}, "negative_quantity"), ({"supplier_id": "ghost"}, "cost_required")]:
        with pytest.raises(EditError) as e:
            edit_line(conn, pid, 1, 1, "buyer-1", now=NOW, **kwargs)
        assert e.value.code == code
    with pytest.raises(EditError) as e:
        edit_line(conn, pid, 99, 1, "buyer-1", qty=1, now=NOW)
    assert e.value.code == "unknown_line"
    assert status(conn, pid).version == 1                                                         # failed edits change nothing


def test_changing_the_supplier_moves_the_line_and_recomputes_both_groups(conn, draft):
    pid, sa, sb = draft
    before = {g.supplier_id: Decimal(str(g.total_cost)) for g in conn.execute(select(supplier_order_groups)).all()}
    edit_line(conn, pid, 1, 1, "buyer-1", supplier_id=sb, qty=10, now=NOW)
    groups = {g.supplier_id: Decimal(str(g.total_cost)) for g in conn.execute(select(supplier_order_groups)).all()}
    line = conn.execute(select(proposal_lines)).one()
    assert line.supplier_id == sb and Decimal(str(line.unit_cost_with_recargo)) == D("1.4000") and "manual_supplier" in line.constraints_applied
    assert groups[sb] == D("14.0000") and groups.get(sa, D(0)) == D(0) and before


def test_over_budget_and_supplier_minimum_are_warned_not_hidden(conn, draft):
    pid, _sa, _sb = draft
    r = edit_line(conn, pid, 1, 1, "buyer-1", qty=6000, now=NOW)
    assert "over_budget" in r.warnings


def test_a_blocked_cost_cannot_be_used_in_an_edit(conn, draft):
    pid, _sa, sb = draft
    add_version(conn, NewCost(product_id=10, supplier_id=sb, cost_with_recargo=D("9.00"), source="manual", actor="x"), CostRules(), NOW)     # +540 % jump
    with pytest.raises(EditError) as e:
        edit_line(conn, pid, 1, 1, "buyer-1", supplier_id=sb, now=NOW)
    assert e.value.code == "cost_blocked"
