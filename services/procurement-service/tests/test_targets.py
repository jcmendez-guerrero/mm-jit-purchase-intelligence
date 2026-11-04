"""T083: replenishment targets (H = 7 days + lead time, inventory position, expiring lots)."""

from builders import fallback_forecast, flat_forecast, linear_forecast, offer, variant
from proposals.targets import compute_target


def target(**kw):
    lead = kw.pop("lead", 3)
    return compute_target(variant(1, [offer("S", "1", lead=lead)], **kw), lead)


def test_protection_horizon_is_seven_days_plus_lead_time():
    assert target(lead=3).horizon_days == 10 and target(lead=0).horizon_days == 7 and target(lead=14).horizon_days == 21


def test_levels_are_interpolated_between_stored_horizons():
    t = target(lead=3, on_hand=0)                  # q(h) = 2h -> up_to(10) = 20, reorder point = q(lead 3) = 6
    assert (t.order_up_to, t.reorder_point, t.need) == (20, 6, 20)


def test_below_the_first_stored_horizon_scales_from_zero_and_beyond_the_last_proportionally():
    assert target(lead=0).order_up_to == 14        # H = 7
    assert target(lead=60).order_up_to == 134      # H = 67 > 42: q(42)=84 scaled by 67/42 = 133.99 -> ceil


def test_an_order_is_needed_only_when_the_position_is_at_or_below_the_reorder_point():
    assert target(on_hand=6).need == 14            # 20 - 6
    assert target(on_hand=7).need == 0 and target(on_hand=7).inventory_position == 7


def test_inbound_counts_only_when_it_arrives_within_the_horizon():
    assert target(on_hand=0, inbound=[(10, 5)]).inventory_position == 10
    assert target(on_hand=0, inbound=[(10, 12)]).inventory_position == 0           # H is 10 days
    assert target(on_hand=0, inbound=[(10, 5)]).need == 0                           # position 10 is above the reorder point 6
    assert target(on_hand=0, inbound=[(5, 5)]).need == 15                           # position 5 <= 6: order up to 20
    t = target(on_hand=0, inbound=[(10, 10)])
    assert t.inbound_counted == 10


def test_lots_expiring_before_the_horizon_do_not_count_as_stock():
    t = target(on_hand=30, expiring=25)
    assert t.usable_on_hand == 5 and t.need == 15 and t.expiring_qty == 25
    assert target(on_hand=30, expiring=0).need == 0


def test_stock_that_already_covers_the_horizon_needs_no_order():
    t = target(on_hand=100)
    assert t.need == 0 and t.inventory_position == 100


def test_ineligible_products_use_the_conservative_min_and_max_and_say_so():
    t = target(forecast=fallback_forecast(3, 9), on_hand=0)
    assert t.fallback and t.expected_demand is None and t.safety_stock is None and t.policy == "minmax_conservative"
    assert t.order_up_to > 0 and t.reorder_point <= t.order_up_to and t.need == t.order_up_to
    assert target(forecast=fallback_forecast(3, 9), on_hand=t.order_up_to).need == 0


def test_eligible_target_reports_expected_demand_and_safety_stock():
    t = target(forecast=linear_forecast(rate=1.0, k=2.0), on_hand=0)
    assert t.expected_demand == 10.0 and t.safety_stock == t.order_up_to - 10 and t.safety_stock > 0


def test_higher_service_level_never_lowers_the_target():
    fc = linear_forecast()
    # quantile table is level-independent in this builder, so use real distinct levels
    from proposals.model import Forecast, HorizonForecast

    fc = Forecast({h: HorizonForecast(h * 1.0, {"0.85": h, "0.90": h + 2, "0.95": h + 4, "0.97": h + 6, "0.99": h + 9}) for h in (7, 14, 21, 28, 42)}, "p", True)
    lo = compute_target(variant(1, [offer("S", "1")], fc, level="0.85"), 3)
    hi = compute_target(variant(1, [offer("S", "1")], fc, level="0.99"), 3)
    assert hi.order_up_to > lo.order_up_to


def test_service_level_between_stored_keys_rounds_up_to_the_next_stored_level():
    from proposals.model import Forecast, HorizonForecast

    fc = Forecast({h: HorizonForecast(float(h), {"0.90": h, "0.95": h + 5, "0.99": h + 9}) for h in (7, 14, 21, 28, 42)}, "p", True)
    t = compute_target(variant(1, [offer("S", "1")], fc, level="0.93"), 0)
    assert t.order_up_to == 12                      # 0.95 key at H=7


def test_clinically_critical_product_with_no_stock_always_gets_at_least_one_unit():
    from proposals.model import Forecast, HorizonForecast

    fc = Forecast({h: HorizonForecast(0.1, {"0.95": 1}) for h in (7, 14, 21, 28, 42)}, "p", True)
    t = compute_target(variant(1, [offer("S", "1")], fc, critical=True), 3)
    assert t.need >= 1
    assert flat_forecast()  # builder sanity
