"""T030: approval eligibility is decided from the mirrored role directory, so a real approval needs two real eligible people."""

from datetime import timedelta
from decimal import Decimal

import pytest
from approvals.workflow import ApprovalError, decide, submit
from builders import flat_forecast, inputs, offer, terms, variant
from conftest import NOW, add_supplier
from costs.rules import CostRules
from costs.store import NewCost, add_version
from mmi_common.auth import Principal
from proposals.generate import generate, store
from users.directory import ConnUserDirectory, set_roles

D = Decimal


@pytest.fixture
def draft(conn):
    sa = add_supplier(conn, 1, "A")
    add_version(conn, NewCost(product_id=10, supplier_id=sa, cost_with_recargo=D("1.00"), source="manual", actor="x", pack_size=6, min_order_qty=0), CostRules(), NOW)
    d = generate(inputs([variant(1, [offer(sa, "1.00", pack=6)], flat_forecast(1.0))], [terms(sa)]), 10)
    return store(conn, d, "buyer-1", "2026-W46", D("1000"), NOW)


def approver(conn, name, active=True):
    set_roles(conn, name, ["viewer", "approver"], "bff", active=active, now=NOW)


def who(subject, age_min=1):
    return Principal(subject, frozenset({"approver"}), NOW - timedelta(minutes=age_min))


def test_nobody_mirrored_means_submission_is_refused(conn, draft):
    with pytest.raises(ApprovalError) as e:
        submit(conn, draft, "buyer-1", 1, ConnUserDirectory(conn), NOW)
    assert e.value.code == "no_eligible_approver"


def test_the_creator_being_the_only_approver_is_not_enough(conn, draft):
    approver(conn, "buyer-1")
    with pytest.raises(ApprovalError) as e:
        submit(conn, draft, "buyer-1", 1, ConnUserDirectory(conn), NOW)
    assert e.value.code == "no_eligible_approver"


def test_a_deactivated_approver_does_not_count(conn, draft):
    approver(conn, "approver-1", active=False)
    with pytest.raises(ApprovalError):
        submit(conn, draft, "buyer-1", 1, ConnUserDirectory(conn), NOW)


def test_one_other_mirrored_approver_allows_submission_and_a_fresh_second_factor_approves(conn, draft):
    approver(conn, "approver-1")
    approver(conn, "approver-2")
    submit(conn, draft, "buyer-1", 1, ConnUserDirectory(conn), NOW)
    decide(conn, draft, who("approver-2"), 1, now=NOW)


def test_the_creator_cannot_approve_even_when_mirrored_as_an_approver(conn, draft):
    approver(conn, "buyer-1")
    approver(conn, "approver-2")
    submit(conn, draft, "buyer-1", 1, ConnUserDirectory(conn), NOW)
    with pytest.raises(ApprovalError):
        decide(conn, draft, who("buyer-1"), 1, now=NOW)


def test_a_stale_second_factor_is_refused_and_a_role_removed_after_submission_is_not_an_approver(conn, draft):
    approver(conn, "approver-2")
    submit(conn, draft, "buyer-1", 1, ConnUserDirectory(conn), NOW)
    with pytest.raises(ApprovalError) as e:
        decide(conn, draft, who("approver-2", age_min=30), 1, now=NOW)
    assert e.value.code == "mfa_required"
    set_roles(conn, "approver-2", ["viewer"], "bff", now=NOW, revision=5)
    assert "approver-2" not in ConnUserDirectory(conn).active_approvers()
