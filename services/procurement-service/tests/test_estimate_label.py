"""T175 (FR-008): a line whose forecast was extended with imported estimates says so in its explanation; nothing else changes."""

from builders import fallback_forecast, flat_forecast, offer, variant
from proposals.generate import generate
from proposals.model import Forecast, ProposalInputs, SupplierTermsIn
from proposals.targets import compute_target
from test_inputs import TODAY


def with_reasons(fc: Forecast, *reasons: str) -> Forecast:
    return Forecast(fc.horizons, fc.policy, fc.eligible, tuple(reasons))


def line_for(fc: Forecast):
    v = variant(1, [offer("A", "1.00")], fc)
    d = generate(ProposalInputs(TODAY, (v,), {"A": SupplierTermsIn("A")}, None), 5)
    return d.lines[0]


def test_an_eligible_forecast_extended_with_seeds_is_labelled_as_imported_estimates():
    ln = line_for(with_reasons(flat_forecast(2.0), "seed_used"))
    assert ln.explanation["forecast_basis"] == "imported_estimates"


def test_an_ordinary_forecast_is_labelled_as_actual_demand():
    assert line_for(flat_forecast(2.0)).explanation["forecast_basis"] == "actual_demand"


def test_a_conservative_min_max_line_is_never_called_estimate_based():
    ln = line_for(with_reasons(fallback_forecast(), "seed_used"))             # not forecast-eligible: nothing is rested on the seeds
    assert ln.explanation["forecast_basis"] == "actual_demand"


def test_the_label_does_not_change_the_quantities():
    a = line_for(with_reasons(flat_forecast(2.0), "seed_used"))
    b = line_for(flat_forecast(2.0))
    assert (a.qty, a.explanation["order_up_to"], a.explanation["reorder_point"]) == (b.qty, b.explanation["order_up_to"], b.explanation["reorder_point"])


def test_the_target_carries_the_flag():
    v = variant(1, [offer("S", "1")], with_reasons(flat_forecast(2.0), "seed_used"))
    assert compute_target(v, 3).estimate_based is True
    assert compute_target(variant(1, [offer("S", "1")]), 3).estimate_based is False
