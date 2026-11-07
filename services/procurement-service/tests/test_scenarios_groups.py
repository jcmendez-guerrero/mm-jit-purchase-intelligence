"""T176 (FR-029): each supplier group of a scenario result carries lines, quantities, costs, shipping, discount, total and budget use, and they add up."""

from decimal import Decimal

from conftest import NOW
from scen import Blob, base, suppliers
from scenarios import store as sc
from scenarios.engine import ScenarioParams, SupplierDelta

D = Decimal


def make(conn, tmp_path, params, key):
    sa, sb = suppliers(conn)
    return sc.create(conn, Blob(tmp_path), "Escenario", params(sa, sb), base(sa, sb), "buyer-1", key, NOW)


def test_every_group_shows_its_parts_and_they_add_up_to_the_order_total(conn, tmp_path):
    out = make(conn, tmp_path, lambda a, b: ScenarioParams(supplier_deltas={a: SupplierDelta(delivery_charge=D("4.50"))}), "k-grp-00001")
    used = [r for r in out["results"] if r["lines"]]
    assert used
    for r in used:
        subtotal, ship, disc, total = D(r["subtotal"]), D(r["delivery_charge"]), D(r["discount"]), D(r["order_total"])
        assert total == subtotal + ship - disc, r["supplier_name"]
        assert sum(D(ln["line_total"]) for ln in r["lines"]) == subtotal
        assert all(ln["qty"] > 0 and D(ln["unit_cost"]) > 0 for ln in r["lines"])
        assert isinstance(r["free_delivery"], bool)


def test_the_stored_group_survives_a_reload(conn, tmp_path):
    out = make(conn, tmp_path, lambda a, b: ScenarioParams(), "k-grp-00002")
    again = sc.get(conn, out["id"])
    assert [(r["supplier_id"], r["subtotal"], r["delivery_charge"], r["discount"], r["free_delivery"]) for r in again["results"]] == \
           [(r["supplier_id"], r["subtotal"], r["delivery_charge"], r["discount"], r["free_delivery"]) for r in out["results"]]
