"""T045 (spec edge cases): a deactivated supplier or an unconfirmed cost is flagged, never repriced silently; a non-EUR supplier keeps its original amount and rate.

The detailed cases are covered by test_supplier_deactivation.py, test_non_eur_supplier.py and test_cost_provenance_difference.py; these checks tie them to the proposal.
"""

from builders import flat_forecast, inputs, offer, terms, variant
from proposals.generate import generate


def test_an_unconfirmed_abnormal_cost_is_not_used_and_the_reason_is_shown():
    d = generate(inputs([variant(1, [offer("A", "0.10", status="blocked_jump"), offer("B", "1.00")], flat_forecast(1.0))], [terms("A"), terms("B")]), 10)
    ln = d.lines[0]
    assert ln.supplier_id == "B" and {"supplier_id": "A", "reason": "cost_blocked"} in ln.explanation["supplier"]["rejected"]


def test_a_disabled_supplier_is_listed_as_rejected_not_silently_ignored():
    from proposals.model import SupplierTermsIn

    ts = [SupplierTermsIn("A", disabled=True), SupplierTermsIn("B")]
    d = generate(inputs([variant(1, [offer("A", "0.50"), offer("B", "1.00")], flat_forecast(1.0))], ts), 10)
    assert d.lines[0].supplier_id == "B" and {"supplier_id": "A", "reason": "supplier_disabled"} in d.lines[0].explanation["supplier"]["rejected"]
