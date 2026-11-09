"""T014 (FR-037): a proposal with a line for a deactivated supplier cannot be submitted or approved until it is reallocated or the supplier is back.

The preview, confirmation and review item of deactivation itself are covered in test_suppliers_service.py.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from approvals.workflow import ApprovalError, decide, submit
from builders import flat_forecast, inputs, offer, terms, variant
from conftest import NOW, add_supplier
from costs.rules import CostRules
from costs.store import NewCost, add_version
from db.tables import approvals
from mmi_common.auth import Principal
from proposals.generate import generate, store
from sqlalchemy import func, select
from suppliers.service import deactivate_supplier, reactivate_supplier
from users.directory import ConnUserDirectory, set_roles

D = Decimal
CODE = "proposal_has_deactivated_supplier"


@pytest.fixture
def draft(conn):
    sa = add_supplier(conn, 1, "A")
    add_version(conn, NewCost(product_id=10, supplier_id=sa, cost_with_recargo=D("1.00"), source="manual", actor="x", pack_size=6, min_order_qty=0), CostRules(), NOW)
    d = generate(inputs([variant(1, [offer(sa, "1.00", pack=6)], flat_forecast(1.0))], [terms(sa)]), 10)
    return sa, store(conn, d, "buyer-1", "2026-W46", D("1000"), NOW)


def two_approvers(conn):
    for name in ("approver-1", "approver-2"):
        set_roles(conn, name, ["viewer", "approver"], "bff", active=True, now=NOW)


def approver(subject="approver-2"):
    return Principal(subject, frozenset({"approver"}), NOW - timedelta(minutes=1))


def test_a_draft_with_a_deactivated_supplier_cannot_be_submitted(conn, draft):
    sa, pid = draft
    two_approvers(conn)
    deactivate_supplier(conn, sa, "buyer-1", confirm=True, now=NOW)
    with pytest.raises(ApprovalError) as e:
        submit(conn, pid, "buyer-1", 1, ConnUserDirectory(conn), NOW)
    assert e.value.code == CODE


def test_a_submitted_proposal_cannot_be_approved_after_its_supplier_is_deactivated(conn, draft):
    sa, pid = draft
    two_approvers(conn)
    submit(conn, pid, "buyer-1", 1, ConnUserDirectory(conn), NOW)
    deactivate_supplier(conn, sa, "buyer-1", confirm=True, now=NOW)
    with pytest.raises(ApprovalError) as e:
        decide(conn, pid, approver(), 1, now=NOW)
    assert e.value.code == CODE
    assert conn.execute(select(func.count()).select_from(approvals)).scalar() == 0           # no approval was recorded


def test_reactivating_the_supplier_lifts_the_block(conn, draft):
    sa, pid = draft
    two_approvers(conn)
    deactivate_supplier(conn, sa, "buyer-1", confirm=True, now=NOW)
    reactivate_supplier(conn, sa, "buyer-1", now=NOW)
    submit(conn, pid, "buyer-1", 1, ConnUserDirectory(conn), NOW)
    decide(conn, pid, approver(), 1, now=NOW)


def test_a_rejection_is_still_possible_so_the_buyer_can_reallocate(conn, draft):
    sa, pid = draft
    two_approvers(conn)
    submit(conn, pid, "buyer-1", 1, ConnUserDirectory(conn), NOW)
    deactivate_supplier(conn, sa, "buyer-1", confirm=True, now=NOW)
    decide(conn, pid, approver(), 1, approve=False, now=NOW)                                  # back to draft; nothing raised


def test_a_proposal_without_that_supplier_is_not_affected(conn, draft):
    _, pid = draft
    other = add_supplier(conn, 2, "B")
    two_approvers(conn)
    deactivate_supplier(conn, other, "buyer-1", confirm=True, now=NOW)
    submit(conn, pid, "buyer-1", 1, ConnUserDirectory(conn), NOW)
