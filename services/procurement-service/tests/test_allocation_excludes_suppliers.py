"""T043 (FR-017, SC-005): deactivated and non-purchasing suppliers never receive proposal lines; the report says why."""

from datetime import date
from decimal import Decimal

from conftest import NOW, add_supplier
from costs.rules import CostRules
from costs.store import NewCost, add_version
from db.tables import suppliers
from proposals.generate import generate
from proposals.inputs import InputsProvider
from sqlalchemy import update
from test_inputs import ELIGIBLE, Src, fc, stock, sv

D = Decimal
TODAY = date(2026, 11, 9)


def cost(conn, sid, pid, value):
    return add_version(conn, NewCost(product_id=pid, supplier_id=sid, cost_with_recargo=D(value), source="siweb_product_supplier", actor="siweb-import"), CostRules(), NOW)


def build(conn):
    provider = InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE)))
    return provider.build(conn, TODAY), provider.report


def setup(conn):
    cheap, other = add_supplier(conn, 1, "Barato"), add_supplier(conn, 2, "Caro")
    cost(conn, cheap, 10, "1.00")
    cost(conn, other, 10, "2.00")
    return cheap, other


def test_both_suppliers_are_offered_when_active_and_purchasing(conn):
    cheap, other = setup(conn)
    inputs, _ = build(conn)
    assert {o.supplier_id for o in inputs.variants[0].offers} == {cheap, other}


def test_a_deactivated_supplier_gets_no_offer_and_the_other_serves_the_line(conn):
    cheap, other = setup(conn)
    conn.execute(update(suppliers).where(suppliers.c.id == cheap).values(status="deactivated"))
    inputs, report = build(conn)
    assert {o.supplier_id for o in inputs.variants[0].offers} == {other}
    assert (1, cheap) in report.disabled_pairs
    draft = generate(inputs, 10)
    assert draft.lines and {line.supplier_id for line in draft.lines} == {other}


def test_a_non_purchasing_supplier_is_never_proposed(conn):
    cheap, other = setup(conn)
    conn.execute(update(suppliers).where(suppliers.c.id == cheap).values(classification="non_purchasing"))
    inputs, report = build(conn)
    assert {o.supplier_id for o in inputs.variants[0].offers} == {other} and (1, cheap) in report.disabled_pairs


def test_unclassified_imported_suppliers_are_not_blocked_but_wait_for_the_buyer(conn):
    cheap, _ = setup(conn)
    conn.execute(update(suppliers).where(suppliers.c.id == cheap).values(classification="unclassified"))
    inputs, _ = build(conn)
    assert cheap in {o.supplier_id for o in inputs.variants[0].offers}


def test_without_any_active_supplier_the_variant_is_reported_without_cost(conn):
    setup(conn)
    conn.execute(update(suppliers).values(status="deactivated"))
    inputs, report = build(conn)
    assert not inputs.variants and report.without_cost == [1]
