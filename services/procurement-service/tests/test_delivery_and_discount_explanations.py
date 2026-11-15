"""T031/T032 (FR-004, US4.2-3): the cheaper of reallocation and shortfall is chosen and shown; a held discount applies and is reported; absent discounts are not invented."""

from decimal import Decimal

from builders import flat_forecast, inputs, offer, terms, variant
from proposals.generate import generate
from proposals.model import Discount, SupplierTermsIn

D = Decimal


def test_a_supplier_that_cannot_meet_its_minimum_loses_the_line_to_a_cheaper_total_and_the_alternatives_are_shown():
    d = generate(inputs([variant(1, [offer("A", "1.00"), offer("B", "1.10")], flat_forecast(1.0))], [terms("A", min_value="20"), terms("B")]), 10)
    ln = d.lines[0]
    assert ln.supplier_id == "B" and {a["supplier_id"] for a in ln.explanation["supplier"]["alternatives"]} == {"A", "B"}


def test_when_no_other_supplier_exists_the_shortfall_is_flagged_with_an_accept_option_and_its_cost():
    d = generate(inputs([variant(1, [offer("A", "1.00")], flat_forecast(1.0))], [terms("A", min_value="12")]), 10)
    g = d.groups[0]
    assert g.minimum_status == "shortfall" and g.options[0]["kind"] == "accept" and g.options[0]["cost_delta"] == "0"


def test_a_held_discount_applies_once_its_threshold_is_crossed_and_is_zero_otherwise():
    t = SupplierTermsIn("A", discounts=(Discount("percent", "order_value", D("5"), D("10")),))
    over = generate(inputs([variant(1, [offer("A", "1.00")], flat_forecast(2.0))], [t]), 10).groups[0]
    assert over.discount > 0 and over.total == over.subtotal - over.discount + over.delivery_charge
    none = generate(inputs([variant(1, [offer("A", "1.00")], flat_forecast(2.0))], [terms("A")]), 10).groups[0]
    assert none.discount == 0
