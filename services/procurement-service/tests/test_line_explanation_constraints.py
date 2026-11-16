"""T007 (FR-003, FR-004, US1.2-3): rounding to a pack and an unmeetable supplier minimum are named on the line and in the group, with their cost effect."""

from builders import flat_forecast, inputs, offer, terms, variant
from proposals.generate import generate


def test_a_pack_rounded_line_names_the_pack_multiple():
    d = generate(inputs([variant(1, [offer("A", "1.00", pack=6)], flat_forecast(1.1))], [terms("A")]), 10)
    ln = d.lines[0]
    assert ln.qty % 6 == 0 and "pack_multiple" in ln.explanation["constraints"]


def test_an_unmeetable_minimum_is_flagged_as_a_shortfall_with_its_value():
    d = generate(inputs([variant(1, [offer("A", "1.00", pack=6)], flat_forecast(1.1))], [terms("A", min_value="500")]), 10)
    g = d.groups[0]
    assert g.minimum_status == "shortfall" and "supplier_minimum_shortfall" in d.lines[0].explanation["constraints"]
    assert g.options and g.options[0]["detail"]["shortfall_value_ticks"] > 0 and {"kind", "cost_delta"} <= set(g.options[0])
