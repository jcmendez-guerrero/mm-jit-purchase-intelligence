"""T136: minimum order, lead time, shipping, pack multiple and budget changes alter the allocation, and the change says why."""

from decimal import Decimal

import pytest
from conftest import NOW
from scen import Blob, base, suppliers
from scenarios import store as sc
from scenarios.engine import ScenarioParams, SupplierDelta

D = Decimal


def run(conn, tmp_path, params, key, **kw):
    sa, sb = suppliers(conn)
    return sa, sb, sc.create(conn, Blob(tmp_path), "Escenario", params(sa, sb), base(sa, sb, **kw), "buyer-1", key, NOW)


def suppliers_used(out):
    return {r["supplier_name"] for r in out["results"] if r["lines"]}


def test_the_baseline_buys_everything_from_the_cheaper_supplier(conn, tmp_path):
    _, _, out = run(conn, tmp_path, lambda a, b: ScenarioParams(), "k-con-00001")
    assert suppliers_used(out) == {"Proveedor A"} and out["summary"]["changes"] == [] and D(out["summary"]["delta_total"]) == 0


@pytest.mark.parametrize("name,delta,reason", [
    ("pedido mínimo", SupplierDelta(min_order_value=D("100")), "min_order_value_changed"),
    ("múltiplo de envase", SupplierDelta(pack_multiple=24), "pack_multiple_changed"),
    ("gastos de envío", SupplierDelta(delivery_charge=D("50")), "delivery_charge_changed"),
    ("plazo de entrega", SupplierDelta(lead_time_days=20), "lead_time_days_changed"),
])
def test_each_supplier_term_change_moves_the_order_to_the_other_supplier_and_names_the_term(conn, tmp_path, name, delta, reason):
    sa, sb, out = run(conn, tmp_path, lambda a, b: ScenarioParams(supplier_deltas={a: delta}), f"k-con-{abs(hash(name)) % 10**8:08d}")
    assert suppliers_used(out) == {"Proveedor B"} and D(out["summary"]["delta_total"]) == D("6.00")
    changes = out["summary"]["changes"]
    assert len(changes) == 3 and all(c["supplier_before"] == sa and c["supplier_after"] == sb and reason in c["reasons"] for c in changes)


def test_disabling_a_supplier_is_named_as_the_reason(conn, tmp_path):
    _sa, _, out = run(conn, tmp_path, lambda a, b: ScenarioParams(disabled_suppliers=(a,)), "k-con-disable")
    assert all("supplier_disabled" in c["reasons"] for c in out["summary"]["changes"]) and suppliers_used(out) == {"Proveedor B"}


def test_a_budget_below_the_need_is_reported_not_silently_cut(conn, tmp_path):
    _, _, out = run(conn, tmp_path, lambda a, b: ScenarioParams(budget=D("20")), "k-con-budget")
    s = out["summary"]
    assert D(s["scenario"]["over_budget"]) == D("10.00") and s["scenario"]["lines"] == 3 and s["scenario"]["utilisation"] == "1.5000"
    assert any(c["key"] == "budget" for c in s["binding"])


def test_a_service_level_change_is_recorded_as_a_reason_when_quantities_move(conn, tmp_path):
    _, _, out = run(conn, tmp_path, lambda a, b: ScenarioParams(service_level_delta=D("0.04")), "k-con-service")
    for c in out["summary"]["changes"]:
        assert "service_level_changed" in c["reasons"]
    assert out["parameters"]["service_level_delta"] == "0.04"


def test_a_free_delivery_threshold_that_is_reached_is_a_binding_constraint(conn, tmp_path):
    sa, _, out = run(conn, tmp_path, lambda a, b: ScenarioParams(), "k-con-free", a_free="30", a_charge="5")
    assert any(c["key"] == f"free_delivery:{sa}" for c in out["summary"]["binding"]) and D(out["summary"]["scenario"]["total"]) == D("30.00")
