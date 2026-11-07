"""T073: earlier runs are unchanged, later runs use the new version and record it."""

from datetime import date, timedelta
from decimal import Decimal

from conftest import NOW, add_supplier
from db.tables import proposals
from policies.service import PolicyValues, save_policy
from proposals.generate import generate, store
from proposals.inputs import InputsProvider
from sqlalchemy import select
from test_inputs import ELIGIBLE, Src, cost, fc, stock, sv

D = Decimal
TODAY = date(2026, 11, 9)


def provider():
    return InputsProvider(Src(stock(sv(1, 10, on_hand=0))), Src(fc(v1=ELIGIBLE)))


def test_the_service_level_in_force_on_the_run_date_is_used(conn):
    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    save_policy(conn, "global", "*", PolicyValues(service_level=D("0.90")), "b", today=TODAY)
    save_policy(conn, "global", "*", PolicyValues(service_level=D("0.99")), "b", valid_from=TODAY + timedelta(days=7), expected_revision=1, today=TODAY)
    now_run, later_run = provider().build(conn, TODAY), provider().build(conn, TODAY + timedelta(days=7))
    assert now_run.variants[0].service_level == D("0.90") and later_run.variants[0].service_level == D("0.99")
    assert now_run.policy_versions == {"global:*": 1} and later_run.policy_versions == {"global:*": 2}


def test_a_later_edit_never_rewrites_an_earlier_run(conn):
    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    save_policy(conn, "global", "*", PolicyValues(service_level=D("0.90")), "b", today=TODAY)
    before = provider().build(conn, TODAY)
    save_policy(conn, "global", "*", PolicyValues(service_level=D("0.99")), "b", valid_from=TODAY + timedelta(days=1), expected_revision=1, today=TODAY)
    assert provider().build(conn, TODAY) == before                                       # same date, same inputs: identical


def test_a_stored_proposal_records_the_policy_revisions_used(conn):
    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    save_policy(conn, "global", "*", PolicyValues(service_level=D("0.97"), min_units=1), "b", today=TODAY)
    inp = provider().build(conn, TODAY)
    pid = store(conn, generate(inp, 5), "buyer-1", "2026-W46", None, NOW)
    assert conn.execute(select(proposals.c.policy_version_ids).where(proposals.c.id == pid)).scalar() == {"global:*": 1}


def test_a_budget_cap_in_the_policies_limits_the_proposal_budget(conn):
    from policies.service import save_budget_cap

    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    save_budget_cap(conn, "week", "global", None, D("250"), "b", today=TODAY)
    assert provider().build(conn, TODAY).budget == D("250")
