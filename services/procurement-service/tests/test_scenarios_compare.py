"""T014 (FR-007, US2.2-3): a changed constraint changes only what it touches, every change has a reason, and scenarios compare side by side."""

from decimal import Decimal

from conftest import NOW
from scen import Blob, base, suppliers
from scenarios import store as sc
from scenarios.engine import ScenarioParams, SupplierDelta

D = Decimal


def test_a_change_to_one_supplier_leaves_the_other_suppliers_lines_alone_and_explains_the_rest(conn, tmp_path):
    sa, sb = suppliers(conn)
    out = sc.create(conn, Blob(tmp_path), "B envio", ScenarioParams(supplier_deltas={sb: SupplierDelta(delivery_charge=D("9"))}), base(sa, sb), "buyer-1", "k-cmp-00001", NOW)
    assert out["summary"]["changes"] == []                       # nobody buys from B, so nothing moves
    out2 = sc.create(conn, Blob(tmp_path), "A minimo", ScenarioParams(supplier_deltas={sa: SupplierDelta(min_order_value=D("500"))}), base(sa, sb), "buyer-1", "k-cmp-00002", NOW)
    assert out2["summary"]["changes"] and all(c["reasons"] for c in out2["summary"]["changes"])


def test_two_scenarios_compare_by_total_supplier_spend_and_ranked_sensitivity(conn, tmp_path):
    sa, sb = suppliers(conn)
    one = sc.create(conn, Blob(tmp_path), "Sin A", ScenarioParams(disabled_suppliers=(sa,)), base(sa, sb), "buyer-1", "k-cmp-00003", NOW)
    two = sc.create(conn, Blob(tmp_path), "Envio gratis", ScenarioParams(), base(sa, sb, a_free="30", a_charge="5"), "buyer-1", "k-cmp-00004", NOW)
    listed = {x["id"]: x for x in sc.listing(conn)}
    assert D(listed[one["id"]]["delta_total"]) != D(listed[two["id"]]["delta_total"])
    for s in (sc.get(conn, one["id"]), sc.get(conn, two["id"])):
        assert s["results"] and all({"supplier_name", "order_total", "binding_constraints"} <= set(r) for r in s["results"]) and isinstance(s["sensitivity"], list)
