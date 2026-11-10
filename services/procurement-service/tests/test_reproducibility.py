"""T085: proposals are reproducible from inputs and rule versions; storage is idempotent per week."""

from dataclasses import replace
from decimal import Decimal

import pytest
from audit.chain import verify_chain
from builders import TODAY, flat_forecast, inputs, offer, terms, variant
from conftest import NOW
from db.tables import proposal_lines, proposals, replenishment_targets, supplier_order_groups
from proposals import generate as gen
from proposals.generate import ProposalConflictError, generate, store
from proposals.model import RULES_VERSION, inputs_hash
from sqlalchemy import func, select, update

D = Decimal


def sample(cost_b="1.40"):
    return inputs([variant(i, [offer("A", "1.00"), offer("B", cost_b)], flat_forecast(1.0 + i)) for i in range(1, 5)], [terms("A", min_value="10", charge="4"), terms("B")])


def test_same_inputs_regenerate_an_identical_proposal():
    a, b = generate(sample(), 10), generate(sample(), 10)
    assert a == b and a.inputs_hash == b.inputs_hash and a.rule_versions == {"targets": RULES_VERSION, "allocation": RULES_VERSION, "explanation": RULES_VERSION, "solver": "cp-sat"}


def test_any_change_to_the_inputs_or_the_rule_versions_changes_the_hash():
    base = inputs_hash(sample(), gen.RULE_VERSIONS)
    assert inputs_hash(sample("1.41"), gen.RULE_VERSIONS) != base
    assert inputs_hash(replace(sample(), today=TODAY.replace(day=10)), gen.RULE_VERSIONS) != base
    assert inputs_hash(sample(), {**gen.RULE_VERSIONS, "allocation": "2.0.0"}) != base
    assert inputs_hash(sample(), gen.RULE_VERSIONS) == base


def test_every_line_carries_a_structured_explanation():
    d = generate(sample(), 10)
    ln = d.lines[0]
    e = ln.explanation
    assert {"policy", "service_level", "horizon_days", "order_up_to", "reorder_point", "position", "need", "supplier", "cost", "constraints"} <= set(e)
    assert e["supplier"]["chosen"] == ln.supplier_id and {a["supplier_id"] for a in e["supplier"]["alternatives"]} == {"A", "B"}
    assert e["supplier"]["reason"] in {"lowest_cost", "lower_total_with_supplier_terms", "lower_lead_time_risk", "free_delivery_threshold_reached", "only_option", "buyer_override"}
    assert ln.risk in ("low", "medium", "high") and ln.confidence in ("low", "medium", "high")
    assert e["cost"]["source"] and e["position"]["total"] == e["position"]["usable"] + e["position"]["inbound"]


def test_stock_covering_the_horizon_and_expiring_lots_show_in_the_explanation():
    inp = inputs([variant(1, [offer("A", "1")], on_hand=100), variant(2, [offer("A", "1")], on_hand=30, expiring=25)], [terms("A")])
    d = generate(inp, 10)
    assert [ln.variant_id for ln in d.lines] == [2]                                                # variant 1 is covered: no line
    assert "expiring_lots" in d.lines[0].constraints and d.lines[0].explanation["position"]["expiring"] == 25


def test_optimiser_is_compared_with_the_greedy_baseline():
    d = generate(sample(), 10)
    assert d.optimized_total <= d.greedy_total and d.solver_status in ("optimal", "feasible")


def test_stored_proposal_has_lines_targets_groups_and_an_audit_trail(conn):
    d = generate(sample(), 10)
    pid = store(conn, d, "buyer-1", "2026-W46", NOW and D("5000"), NOW)
    p = conn.execute(select(proposals)).one()
    assert (p.id, p.status, p.version, p.created_by, p.last_edited_by, p.inputs_hash) == (pid, "draft", 1, "buyer-1", "buyer-1", d.inputs_hash)
    assert p.rule_versions == d.rule_versions
    assert conn.execute(select(func.count()).select_from(proposal_lines)).scalar_one() == len(d.lines)
    assert conn.execute(select(func.count()).select_from(replenishment_targets)).scalar_one() == len(d.targets)
    assert {g.supplier_id for g in conn.execute(select(supplier_order_groups)).all()} == {g.supplier_id for g in d.groups}
    line = conn.execute(select(proposal_lines)).first()
    assert line.explanation["version"] == 1 and line.manual_override is False and Decimal(str(line.line_total)) == Decimal(str(line.unit_cost_with_recargo)) * line.qty
    assert verify_chain(conn).ok


def test_storing_the_same_inputs_twice_returns_the_same_proposal(conn):
    d = generate(sample(), 10)
    a, b = store(conn, d, "buyer-1", "2026-W46", None, NOW), store(conn, generate(sample(), 10), "buyer-2", "2026-W46", None, NOW)
    assert a == b and conn.execute(select(func.count()).select_from(proposals)).scalar_one() == 1


def test_new_inputs_supersede_the_open_proposal_but_never_an_approved_one(conn):
    first = store(conn, generate(sample(), 10), "buyer-1", "2026-W46", None, NOW)
    second = store(conn, generate(sample("1.50"), 10), "buyer-1", "2026-W46", None, NOW)
    status = {r.id: r.status for r in conn.execute(select(proposals)).all()}
    assert status[first] == "superseded" and status[second] == "draft"
    conn.execute(update(proposals).where(proposals.c.id == second).values(status="approved"))
    with pytest.raises(ProposalConflictError):
        store(conn, generate(sample("1.60"), 10), "buyer-1", "2026-W46", None, NOW)
    assert store(conn, generate(sample("1.60"), 10), "buyer-1", "2026-W47", None, NOW)             # another week is independent
