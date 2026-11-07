"""T139: promotion creates a normal draft proposal that needs a different approver with a fresh second factor; a stale scenario is refused."""

from datetime import timedelta
from decimal import Decimal

import pytest
from approvals.workflow import ApprovalError, decide, submit
from conftest import NOW
from db.tables import audit_events, proposals, scenarios
from mmi_common.auth import Principal
from scen import Blob, base, suppliers
from scenarios import store as sc
from scenarios.engine import ScenarioParams
from sqlalchemy import select

D = Decimal
WEEK = "2026-W46"


class Users:
    def active_approvers(self):
        return {"approver-1", "approver-2"}


def ready(conn, tmp_path, key="k-pro-000001"):
    sa, sb = suppliers(conn)
    out = sc.create(conn, Blob(tmp_path), "Sin A", ScenarioParams(disabled_suppliers=(sa,)), base(sa, sb), "buyer-1", key, NOW)
    return sa, sb, out


def test_promotion_stores_a_draft_proposal_created_by_the_promoter_and_marks_the_scenario(conn, tmp_path):
    sa, sb, out = ready(conn, tmp_path)
    res = sc.promote(conn, out["id"], base(sa, sb), "buyer-2", WEEK, NOW)
    p = conn.execute(select(proposals).where(proposals.c.id == res["proposal_id"])).one()
    assert p.status == "draft" and p.created_by == "buyer-2" and p.scenario_id == out["id"] and res["superseded"] == []
    assert conn.execute(select(scenarios.c.status).where(scenarios.c.id == out["id"])).scalar() == "promoted"
    assert [a.action for a in conn.execute(select(audit_events)).all()][-1] == "scenario.promoted"


def test_the_promoter_cannot_approve_their_own_promotion_and_another_approver_needs_a_fresh_second_factor(conn, tmp_path):
    sa, sb, out = ready(conn, tmp_path)
    pid = sc.promote(conn, out["id"], base(sa, sb), "buyer-2", WEEK, NOW)["proposal_id"]
    submit(conn, pid, "buyer-2", 1, Users(), NOW)
    with pytest.raises(ApprovalError):
        decide(conn, pid, Principal("buyer-2", frozenset({"approver"}), NOW - timedelta(minutes=1)), 1, now=NOW)
    with pytest.raises(ApprovalError):
        decide(conn, pid, Principal("approver-1", frozenset({"approver"}), NOW - timedelta(minutes=30)), 1, now=NOW)
    decide(conn, pid, Principal("approver-1", frozenset({"approver"}), NOW - timedelta(minutes=1)), 1, now=NOW)
    assert conn.execute(select(proposals.c.status)).scalar() == "approved"


def test_a_scenario_whose_inputs_changed_is_stale_and_creates_nothing(conn, tmp_path):
    sa, sb, out = ready(conn, tmp_path)
    changed = base(sa, sb, n=4)                                           # one more variant: the recomputed result differs
    with pytest.raises(sc.ScenarioStateError) as e:
        sc.promote(conn, out["id"], changed, "buyer-2", WEEK, NOW)
    assert e.value.code == "scenario_stale" and conn.execute(select(proposals)).all() == []


def test_a_scenario_can_be_promoted_once_and_only_when_ready(conn, tmp_path):
    sa, sb, out = ready(conn, tmp_path)
    sc.promote(conn, out["id"], base(sa, sb), "buyer-2", WEEK, NOW)
    with pytest.raises(sc.ScenarioStateError) as e:
        sc.promote(conn, out["id"], base(sa, sb), "buyer-2", WEEK, NOW)
    assert e.value.code == "scenario_already_promoted"
    with pytest.raises(sc.ScenarioStateError) as e2:
        sc.promote(conn, "nope", base(sa, sb), "buyer-2", WEEK, NOW)
    assert e2.value.code == "unknown_scenario"


def test_promotion_reports_the_draft_it_replaced_and_never_touches_an_approved_week(conn, tmp_path):
    from proposals.generate import ProposalConflictError, generate, store

    sa, sb, out = ready(conn, tmp_path)
    earlier = store(conn, generate(base(sa, sb), 5), "buyer-1", WEEK, None, NOW)
    res = sc.promote(conn, out["id"], base(sa, sb), "buyer-2", WEEK, NOW)
    assert res["superseded"] == [earlier]
    from sqlalchemy import update

    conn.execute(update(proposals).where(proposals.c.id == res["proposal_id"]).values(status="approved"))
    sa2, sb2, out2 = ready_other(conn, tmp_path)
    with pytest.raises(ProposalConflictError):
        sc.promote(conn, out2["id"], base(sa2, sb2), "buyer-2", WEEK, NOW)


def ready_other(conn, tmp_path):
    from db.tables import suppliers as sup
    from sqlalchemy import select as sel

    rows = conn.execute(sel(sup.c.id).order_by(sup.c.external_contact_id)).all()
    sa, sb = rows[0].id, rows[1].id
    out = sc.create(conn, Blob(tmp_path), "Sin B", ScenarioParams(disabled_suppliers=(sb,)), base(sa, sb), "buyer-1", "k-pro-000002", NOW)
    return sa, sb, out
