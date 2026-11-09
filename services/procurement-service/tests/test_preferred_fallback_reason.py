"""T031 (FR-019, decided 2026-11-09): a preferred supplier wins an otherwise equal tie and nothing more; every line says why its supplier was
chosen and why the alternatives were not.
"""

from __future__ import annotations

from builders import flat_forecast, inputs, offer, variant
from proposals.generate import generate
from proposals.model import SupplierTermsIn


def plan(offers, terms):
    return generate(inputs([variant(1, offers, flat_forecast(2.0))], terms), 5).lines[0]


def alternatives(line):
    return {a["supplier_id"]: a for a in line.explanation["supplier"]["alternatives"]}


def test_a_preferred_supplier_wins_an_exact_tie_and_the_line_shows_both_offers():
    line = plan([offer("A", "1.00"), offer("B", "1.00")], [SupplierTermsIn("A"), SupplierTermsIn("B", preferred=True)])
    assert line.supplier_id == "B" and line.explanation["supplier"]["reason"] == "preferred_supplier_on_tie"      # not "lowest cost": A cost the same
    alts = alternatives(line)
    assert set(alts) == {"A", "B"} and alts["B"]["chosen"] is True and alts["A"]["chosen"] is False
    assert alts["A"]["unit_cost"] == alts["B"]["unit_cost"]                       # the buyer can see it was a tie


def test_a_clearly_cheaper_supplier_still_beats_the_preferred_one_and_the_line_says_what_it_cost_instead():
    line = plan([offer("A", "1.00"), offer("B", "1.30")], [SupplierTermsIn("A"), SupplierTermsIn("B", preferred=True)])
    assert line.supplier_id == "A" and line.explanation["supplier"]["reason"] != "preferred_supplier_on_tie"
    alts = alternatives(line)
    assert alts["A"]["chosen"] is True and alts["B"]["chosen"] is False
    assert float(alts["B"]["unit_cost"]) > float(alts["A"]["unit_cost"])


def test_every_line_states_a_reason_for_its_supplier():
    tie = plan([offer("A", "1.00"), offer("B", "1.00")], [SupplierTermsIn("A"), SupplierTermsIn("B", preferred=True)])
    cheaper = plan([offer("A", "1.00"), offer("B", "1.30")], [SupplierTermsIn("A"), SupplierTermsIn("B")])
    only = plan([offer("A", "1.00")], [SupplierTermsIn("A")])
    for line in (tie, cheaper, only):
        assert line.explanation["supplier"]["reason"]
    assert only.explanation["supplier"]["reason"] == "only_option"


def test_a_supplier_that_could_not_serve_the_line_is_listed_with_the_reason():
    disabled = plan([offer("A", "1.00"), offer("B", "2.00")], [SupplierTermsIn("A", disabled=True), SupplierTermsIn("B")])
    assert {"supplier_id": "A", "reason": "supplier_disabled"} in disabled.explanation["supplier"]["rejected"]
    too_slow = plan([offer("A", "1.00", lead=40), offer("B", "2.00", lead=3)], [SupplierTermsIn("A"), SupplierTermsIn("B")])
    assert {"supplier_id": "A", "reason": "lead_time_too_long"} in too_slow.explanation["supplier"]["rejected"]
    assert too_slow.supplier_id == "B"
