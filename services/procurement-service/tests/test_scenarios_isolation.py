"""T135: a scenario never writes live tables or ERP data and is reproducible from the recorded versions."""

from decimal import Decimal

from conftest import NOW
from db.tables import (
    audit_events,
    cost_write_requests,
    outbox,
    policy_sets,
    proposal_lines,
    proposals,
    scenarios,
    supplier_costs,
    supplier_terms,
)
from scen import Blob, base, suppliers
from scenarios import store as sc
from scenarios.engine import ScenarioError, ScenarioParams, SupplierDelta, apply_params
from sqlalchemy import func, select

LIVE = (proposals, proposal_lines, cost_write_requests, supplier_costs, supplier_terms, policy_sets)


def counts(conn, tables):
    return [conn.execute(select(func.count()).select_from(t)).scalar() for t in tables]


def test_creating_a_scenario_writes_only_scenario_tables_the_audit_and_the_ready_event(conn, tmp_path):
    sa, sb = suppliers(conn)
    before = counts(conn, LIVE)
    out = sc.create(conn, Blob(tmp_path), "Sin proveedor A", ScenarioParams(disabled_suppliers=(sa,)), base(sa, sb), "buyer-1", "k-isolation-1", NOW)
    assert out["status"] == "ready" and counts(conn, LIVE) == before
    assert [e.type for e in conn.execute(select(outbox)).all()] == ["procurement.scenario.ready.v1"]
    assert [a.action for a in conn.execute(select(audit_events)).all()] == ["scenario.created"]


def test_applying_parameters_never_mutates_the_base_inputs(conn):
    sa, sb = suppliers(conn)
    b = base(sa, sb)
    snapshot = repr(b)
    apply_params(b, ScenarioParams(budget=Decimal("10"), disabled_suppliers=(sa,), supplier_deltas={sb: SupplierDelta(lead_time_days=9)}))
    assert repr(b) == snapshot


def test_the_same_inputs_and_parameters_give_the_same_result_hash_and_recorded_versions(conn, tmp_path):
    sa, sb = suppliers(conn)
    p = ScenarioParams(disabled_suppliers=(sa,))
    a = sc.create(conn, Blob(tmp_path), "Uno", p, base(sa, sb), "buyer-1", "k-repro-0001", NOW)
    b = sc.create(conn, Blob(tmp_path), "Dos", p, base(sa, sb), "buyer-2", "k-repro-0002", NOW)
    assert a["result_hash"] == b["result_hash"] and a["input_versions"]["inputs_fingerprint"] == b["input_versions"]["inputs_fingerprint"]
    assert a["input_versions"]["rules"]["solver"] == "cp-sat"
    c = sc.create(conn, Blob(tmp_path), "Tres", ScenarioParams(disabled_suppliers=(sb,)), base(sa, sb), "buyer-1", "k-repro-0003", NOW)
    assert c["result_hash"] != a["result_hash"]


def test_the_same_idempotency_key_returns_the_stored_scenario_without_a_second_computation(conn, tmp_path):
    sa, sb = suppliers(conn)
    one = sc.create(conn, Blob(tmp_path), "Uno", ScenarioParams(disabled_suppliers=(sa,)), base(sa, sb), "buyer-1", "k-same-key-1", NOW)
    two = sc.create(conn, Blob(tmp_path), "Otro nombre", ScenarioParams(), base(sa, sb), "buyer-1", "k-same-key-1", NOW)
    assert two["id"] == one["id"] and two["name"] == "Uno"
    assert conn.execute(select(func.count()).select_from(scenarios)).scalar() == 1


def test_invalid_parameters_are_refused_before_anything_is_stored(conn, tmp_path):
    from decimal import Decimal

    sa, sb = suppliers(conn)
    for bad in (ScenarioParams(budget=Decimal("-1")), ScenarioParams(service_level_delta=Decimal("0.9")), ScenarioParams(supplier_deltas={sa: SupplierDelta(pack_multiple=0)}),
                ScenarioParams(supplier_deltas={sa: SupplierDelta(min_order_value=Decimal("50"), free_delivery_threshold=Decimal("10"))})):
        try:
            sc.create(conn, Blob(tmp_path), "x", bad, base(sa, sb), "buyer-1", "k-bad-000001", NOW)
        except ScenarioError as e:
            assert e.code == "scenario_invalid"
        else:
            raise AssertionError("accepted")
    assert conn.execute(select(func.count()).select_from(scenarios)).scalar() == 0
