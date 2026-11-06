"""T079: always-stocked mode - floor, monthly check, nothing automatic, shortfall shown."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from builders import fallback_forecast, offer, variant
from conftest import NOW, add_supplier
from policies.service import PolicyError
from policies.stocking import get_stocking, save_stocking, stocking_map
from proposals.generate import generate
from proposals.inputs import InputsProvider
from proposals.model import VariantInput
from proposals.targets import compute_target
from test_inputs import ELIGIBLE, Src, cost, fc, stock, sv

D = Decimal
TODAY = date(2026, 11, 9)


def with_floor(v, floor=1, monthly=False):
    return VariantInput(**{**v.__dict__, "floor_units": floor, "monthly_check": monthly})


def test_settings_validate_and_are_revisioned(conn):
    with pytest.raises(PolicyError) as e:
        save_stocking(conn, 1, "always_stocked", 0, "b")
    assert e.value.code == "stocking_floor_required"
    for bad in (("planet", 1), ("standard", -1), ("standard", 10_001)):
        with pytest.raises(PolicyError):
            save_stocking(conn, 1, *bad, "b")
    assert save_stocking(conn, 1, "always_stocked", 2, "b", now=NOW) == 1
    assert save_stocking(conn, 1, "always_stocked", 3, "b", expected_revision=1, now=NOW) == 2
    assert get_stocking(conn, 1)["min_floor_units"] == 3 and stocking_map(conn) == {1: ("always_stocked", 3)}
    assert get_stocking(conn, 99) == {"variant_id": 99, "stocking_mode": "standard", "min_floor_units": 0, "revision": 0}


def test_the_floor_forces_a_line_when_there_is_no_forecast_or_no_demand():
    v = variant(1, [offer("s", "1.00")], fallback_forecast(0, 0), on_hand=0)
    assert compute_target(v, 3).need == 0                                                   # without the setting nothing is bought
    t = compute_target(with_floor(v, 2), 3)
    assert t.need == 2 and t.floor_reason == "always_stocked_floor"


def test_the_floor_tops_up_only_what_is_missing():
    v = variant(1, [offer("s", "1.00")], fallback_forecast(0, 0), on_hand=1)
    assert compute_target(with_floor(v, 3), 3).need == 2
    assert compute_target(with_floor(v, 1), 3).need == 0 and compute_target(with_floor(v, 1), 3).floor_reason is None


def test_the_monthly_check_buys_at_least_one_unit_when_nothing_else_is_needed():
    v = variant(1, [offer("s", "1.00")], fallback_forecast(0, 0), on_hand=5)
    t = compute_target(with_floor(v, 1, monthly=True), 3)
    assert t.need == 1 and t.floor_reason == "always_stocked_monthly"
    assert compute_target(with_floor(v, 1, monthly=False), 3).need == 0


def test_the_proposal_line_carries_the_floor_reason():
    v = with_floor(variant(1, [offer("s", "1.00")], fallback_forecast(0, 0), on_hand=0), 2)
    from builders import inputs, terms

    d = generate(inputs([v], [terms("s")]), 5)
    assert d.lines[0].qty >= 2 and d.lines[0].explanation["floor_reason"] == "always_stocked_floor"


def test_the_inputs_builder_includes_unforecast_always_stocked_variants_and_never_orders_by_itself(conn):
    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    save_stocking(conn, 1, "always_stocked", 2, "b", now=NOW)
    inp = InputsProvider(Src(stock(sv(1, 10, on_hand=0))), Src(fc())).build(conn, TODAY)           # no forecast entry for the variant
    v = inp.variants[0]
    assert v.floor_units == 2 and v.monthly_check is True and not v.forecast.eligible and dict(v.policy_info)["stocking"] == "always_stocked"
    from db.tables import proposals

    assert conn.execute(proposals.select()).all() == []                                      # building inputs created nothing: a human generates and approves


def test_the_monthly_check_is_off_when_something_was_bought_in_the_last_30_days(conn):
    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    save_stocking(conn, 1, "always_stocked", 1, "b", now=NOW)
    from db.tables import inbound_order_lines, inbound_orders
    from sqlalchemy import insert

    conn.execute(insert(inbound_orders).values(id="o1", proposal_id="p", supplier_id=sa, status="confirmed", confirmed_by="b", confirmed_at=NOW - timedelta(days=5)))
    conn.execute(insert(inbound_order_lines).values(order_id="o1", variant_id=1, qty=1, confirmed_cost_with_recargo=D("1"), received_qty=0))
    inp = InputsProvider(Src(stock(sv(1, 10, on_hand=5))), Src(fc(v1=ELIGIBLE))).build(conn, TODAY)
    assert inp.variants[0].monthly_check is False


def test_on_request_products_are_never_proposed_and_an_unserved_always_stocked_one_is_reported(conn):
    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    save_stocking(conn, 1, "on_request", 0, "b", now=NOW)
    save_stocking(conn, 2, "always_stocked", 1, "b", now=NOW)                                # product 20 has no supplier cost
    prov = InputsProvider(Src(stock(sv(1, 10), sv(2, 20))), Src(fc(v1=ELIGIBLE)))
    inp = prov.build(conn, TODAY)
    assert inp.variants == () and prov.report.on_request == [1] and prov.report.always_stocked_unserved == [2]
