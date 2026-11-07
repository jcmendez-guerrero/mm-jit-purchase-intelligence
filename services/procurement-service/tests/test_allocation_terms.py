"""T044: the allocation uses the saved terms - disable, preference, discounts, lead time, pack multiples, validity - and cites them."""

from decimal import Decimal

import pytest
from builders import flat_forecast, offer, variant
from conftest import NOW, add_product, add_supplier
from costs.rules import CostRules
from costs.store import NewCost, add_version
from proposals.generate import generate
from proposals.inputs import InputsProvider
from proposals.model import Discount, ProposalInputs, SupplierTermsIn
from terms.overrides import OverrideTerms, save_override
from terms.service import Discount as TermDiscount
from terms.service import Terms, save_terms
from test_inputs import ELIGIBLE, TODAY, Src, fc, stock, sv

D = Decimal


def inp(variants, terms, budget=None):
    return ProposalInputs(TODAY, tuple(variants), {t.supplier_id: t for t in terms}, budget)


def chosen(draft):
    return {ln.variant_id: ln.supplier_id for ln in draft.lines}


def test_a_disabled_supplier_is_never_chosen_even_when_cheapest():
    v = variant(1, [offer("A", "1.00"), offer("B", "2.00")], flat_forecast(2.0))
    d = generate(inp([v], [SupplierTermsIn("A", disabled=True), SupplierTermsIn("B")]), 5)
    assert chosen(d) == {1: "B"}
    assert {"supplier_id": "A", "reason": "supplier_disabled"} in d.lines[0].explanation["supplier"]["rejected"]


def test_the_preferred_supplier_wins_a_tie_and_only_a_tie():
    v = variant(1, [offer("A", "1.00"), offer("B", "1.00")], flat_forecast(2.0))
    assert chosen(generate(inp([v], [SupplierTermsIn("A"), SupplierTermsIn("B", preferred=True)]), 5)) == {1: "B"}
    pricier = variant(1, [offer("A", "1.00"), offer("B", "1.10")], flat_forecast(2.0))
    assert chosen(generate(inp([pricier], [SupplierTermsIn("A"), SupplierTermsIn("B", preferred=True)]), 5)) == {1: "A"}


def test_a_percentage_discount_over_a_value_threshold_changes_the_cheapest_supplier_and_the_total():
    v = variant(1, [offer("A", "1.00"), offer("B", "0.97")], flat_forecast(30.0))          # ~150 units needed
    plain = generate(inp([v], [SupplierTermsIn("A"), SupplierTermsIn("B")]), 5)
    assert chosen(plain) == {1: "B"}
    disc = SupplierTermsIn("A", discounts=(Discount("percent", "order_value", D("100"), D("10")),))
    d = generate(inp([v], [disc, SupplierTermsIn("B")]), 5)
    assert chosen(d) == {1: "A"}
    g = d.groups[0]
    assert g.discount > 0 and g.total == g.subtotal - g.discount + g.delivery_charge
    assert d.optimized_total == sum(x.total for x in d.groups)                               # the solver and the report agree


def test_a_discount_below_its_threshold_does_not_apply():
    v = variant(1, [offer("A", "1.00")], flat_forecast(0.5))
    d = generate(inp([v], [SupplierTermsIn("A", discounts=(Discount("percent", "order_value", D("100000"), D("50")),))]), 5)
    assert d.groups[0].discount == 0


def test_a_units_threshold_amount_discount_applies_and_the_best_qualifying_tier_is_used():
    v = variant(1, [offer("A", "1.00", pack=1)], flat_forecast(20.0))
    tiers = (Discount("amount", "order_units", D("10"), D("5")), Discount("amount", "order_units", D("40"), D("30")), Discount("amount", "order_units", D("5000"), D("999")))
    d = generate(inp([v], [SupplierTermsIn("A", discounts=tiers)]), 5)
    assert d.groups[0].discount == D("30")


def test_a_discount_never_exceeds_the_subtotal():
    v = variant(1, [offer("A", "1.00")], flat_forecast(2.0))
    d = generate(inp([v], [SupplierTermsIn("A", discounts=(Discount("amount", "order_units", D("1"), D("100000")),))]), 5)
    assert d.groups[0].total >= 0 and d.groups[0].discount == d.groups[0].subtotal


def test_minimums_and_free_delivery_are_judged_before_the_discount():
    v = variant(1, [offer("A", "1.00")], flat_forecast(30.0))
    t = SupplierTermsIn("A", free_delivery_threshold=D("100"), delivery_charge=D("9"), discounts=(Discount("percent", "order_value", D("50"), D("50")),))
    g = generate(inp([v], [t]), 5).groups[0]
    assert g.free_delivery is True and g.delivery_charge == 0 and g.discount > 0


# ---- through the real inputs provider and the database: validity windows, overrides, citations ----
def setup(conn):
    sa, sb = add_supplier(conn, 1, "A"), add_supplier(conn, 2, "B")
    add_product(conn, 1, 10)
    for sid, value in ((sa, "1.00"), (sb, "1.30")):
        add_version(conn, NewCost(product_id=10, supplier_id=sid, cost_with_recargo=D(value), source="manual", actor="x", pack_size=1, lead_time_days=6), CostRules(), NOW)
    return sa, sb


def build(conn):
    return InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE))).build(conn, TODAY)


def test_saved_terms_reach_the_next_proposal(conn):
    sa, _sb = setup(conn)
    save_terms(conn, sa, Terms(lead_time_days=2, preferred=True, discounts=(TermDiscount("percent", "order_value", D("1"), D("5")),)), "buyer-1", NOW)
    i = build(conn)
    assert i.suppliers[sa].preferred is True and i.suppliers[sa].discounts[0].value == D("5")
    assert {o.supplier_id: o.lead_time_days for o in i.variants[0].offers}[sa] == 2


def test_a_disabled_supplier_or_pair_is_not_offered(conn):
    sa, sb = setup(conn)
    save_terms(conn, sa, Terms(disabled=True), "b", NOW)
    assert {o.supplier_id for o in build(conn).variants[0].offers} == {sb}
    save_terms(conn, sa, Terms(), "b", NOW, expected_version=1)                               # re-enabled at supplier level
    save_override(conn, 1, sb, OverrideTerms(disabled=True), "b", NOW)
    assert {o.supplier_id for o in build(conn).variants[0].offers} == {sa}


def test_a_product_override_changes_pack_and_lead_for_that_product_only(conn):
    sa, sb = setup(conn)
    save_override(conn, 1, sa, OverrideTerms(pack_multiple=12, lead_time_days=4, min_qty_units=24), "b", NOW)
    o = {x.supplier_id: x for x in build(conn).variants[0].offers}
    assert (o[sa].pack_size, o[sa].lead_time_days, o[sa].min_order_qty) == (12, 4, 24) and (o[sb].pack_size, o[sb].lead_time_days) == (1, 6)


def test_the_proposal_cites_the_terms_versions_it_used(conn):
    sa, _sb = setup(conn)
    save_terms(conn, sa, Terms(lead_time_days=2), "b", NOW)
    save_override(conn, 1, sa, OverrideTerms(pack_multiple=6), "b", NOW)
    draft = generate(build(conn), 5)
    ex = draft.lines[0].explanation["terms"]
    assert ex["supplier_version"] == 1 and ex["override_version"] == 1 and ex["sources"]["lead_time_days"] == "supplier" and ex["sources"]["pack_multiple"] == "override"
    assert draft.terms_versions == {sa: {"supplier": 1, "override": {"1": 1}}} or draft.terms_versions[sa]["supplier"] == 1


def test_the_stored_proposal_records_the_terms_versions(conn):
    from db.tables import proposals
    from proposals.generate import store
    from sqlalchemy import select

    sa, _sb = setup(conn)
    save_terms(conn, sa, Terms(lead_time_days=2), "b", NOW)
    pid = store(conn, generate(build(conn), 5), "buyer-1", "2026-W46", None, NOW)
    row = conn.execute(select(proposals).where(proposals.c.id == pid)).one()
    assert row.terms_version_ids and row.terms_version_ids[sa]["supplier"] == 1


@pytest.mark.parametrize("field", ["disabled", "preferred", "discounts"])
def test_new_input_fields_default_to_neutral(field):
    t = SupplierTermsIn("A")
    assert getattr(t, field) in (False, ())
