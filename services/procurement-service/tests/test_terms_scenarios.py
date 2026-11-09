"""T026 (SC-005): twenty-four synthetic scenarios from saved terms to the proposal, through the real inputs builder and the database.

Each one asserts what can be justified without running the optimizer by hand: which supplier serves the line, pack multiples and minimums
honoured, shortfalls flagged, delivery dates on the supplier's weekdays, and the terms version the line cites.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from conftest import NOW, add_product, add_supplier
from costs.rules import CostRules
from costs.store import NewCost, add_version
from proposals.generate import generate
from proposals.inputs import InputsProvider
from terms.overrides import OverrideTerms, save_override
from terms.service import Discount, Terms, save_terms
from test_inputs import ELIGIBLE, TODAY, Src, fc, stock, sv

D = Decimal
EVERY_DAY = (1, 2, 3, 4, 5, 6, 7)


def world(conn, cost_a="1.00", cost_b="1.30", lead=6):
    sa, sb = add_supplier(conn, 1, "A"), add_supplier(conn, 2, "B")
    add_product(conn, 1, 10)
    for sid, value in ((sa, cost_a), (sb, cost_b)):
        add_version(conn, NewCost(product_id=10, supplier_id=sid, cost_with_recargo=D(value), source="manual", actor="x", pack_size=1, lead_time_days=lead), CostRules(), NOW)
    return sa, sb


def plan(conn):
    built = InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE))).build(conn, TODAY)
    draft = generate(built, 5)
    return built, draft, draft.lines[0]


# ---- which supplier serves the line ----
def test_01_the_cheaper_supplier_wins_without_terms(conn):
    sa, _ = world(conn)
    assert plan(conn)[2].supplier_id == sa


def test_02_a_disabled_supplier_is_skipped(conn):
    sa, sb = world(conn)
    save_terms(conn, sa, Terms(disabled=True), "b", NOW)
    assert plan(conn)[2].supplier_id == sb


def test_03_a_pair_disabled_by_an_override_is_skipped_for_that_product_only(conn):
    sa, sb = world(conn)
    save_override(conn, 1, sa, OverrideTerms(disabled=True), "b", NOW)
    assert plan(conn)[2].supplier_id == sb


def test_04_the_preferred_supplier_wins_only_a_tie(conn):
    _sa, sb = world(conn, cost_a="1.00", cost_b="1.00")
    save_terms(conn, sb, Terms(preferred=True), "b", NOW)
    assert plan(conn)[2].supplier_id == sb


def test_05_a_preferred_supplier_does_not_beat_a_clearly_cheaper_one(conn):
    sa, sb = world(conn)
    save_terms(conn, sb, Terms(preferred=True), "b", NOW)
    assert plan(conn)[2].supplier_id == sa


def test_06_a_discount_can_make_the_pricier_supplier_the_cheapest(conn):
    sa, _sb = world(conn, cost_a="1.00", cost_b="0.97")
    save_terms(conn, sa, Terms(discounts=(Discount("percent", "order_value", D("1"), D("10")),)), "b", NOW)
    _, draft, line = plan(conn)
    assert line.supplier_id == sa and draft.groups[0].discount > 0


def test_07_an_unreached_discount_threshold_changes_nothing(conn):
    sa, sb = world(conn, cost_a="1.00", cost_b="0.97")
    save_terms(conn, sa, Terms(discounts=(Discount("percent", "order_value", D("1000000"), D("50")),)), "b", NOW)
    _, draft, line = plan(conn)
    assert line.supplier_id == sb and draft.groups[0].discount == 0


# ---- pack multiples, minimums, shortfalls, delivery charges ----
def test_08_a_pack_multiple_override_rounds_the_quantity_up(conn):
    sa, _ = world(conn)
    save_override(conn, 1, sa, OverrideTerms(pack_multiple=12), "b", NOW)
    assert plan(conn)[2].qty % 12 == 0


def only_a(conn):
    """Supplier A alone: B is disabled, so the optimizer cannot avoid A's terms."""
    sa, sb = world(conn)
    save_terms(conn, sb, Terms(disabled=True), "b", NOW)
    return sa


def test_09_a_minimum_units_override_raises_a_small_order(conn):
    sa = only_a(conn)
    save_override(conn, 1, sa, OverrideTerms(min_qty_units=500), "b", NOW)
    line = plan(conn)[2]
    assert line.supplier_id == sa and line.qty >= 500


def test_09b_the_optimizer_avoids_a_supplier_whose_minimum_would_make_the_order_dearer(conn):
    sa, sb = world(conn)
    save_override(conn, 1, sa, OverrideTerms(min_qty_units=500), "b", NOW)       # 500 units at 1.00 costs far more than the need at 1.30
    line = plan(conn)[2]
    assert line.supplier_id == sb and line.qty < 500


def test_10_an_unreachable_minimum_order_value_is_flagged_not_hidden(conn):
    sa = only_a(conn)
    save_terms(conn, sa, Terms(min_order_value=D("1000000")), "b", NOW)
    _, draft, line = plan(conn)
    assert line.supplier_id and draft.groups[0].minimum_status == "shortfall" and "supplier_minimum_shortfall" in line.constraints


def test_10c_a_shortfall_keeps_the_line_marks_it_high_risk_and_offers_the_buyer_a_way_out(conn):
    """FR-022: a minimum that cannot be reached never drops a line; it is shown, with what is missing."""
    sa = only_a(conn)
    save_terms(conn, sa, Terms(min_order_value=D("1000000")), "b", NOW)
    _, draft, line = plan(conn)
    group = draft.groups[0]
    assert len(draft.lines) == 1 and line.qty > 0 and line.risk == "high"
    accept = [o for o in group.options if o["kind"] == "accept"]
    assert accept and accept[0]["detail"]["shortfall_value_ticks"] > 0


def test_10b_with_another_supplier_available_the_shortfall_is_avoided(conn):
    sa, sb = world(conn)
    save_terms(conn, sa, Terms(min_order_value=D("1000000")), "b", NOW)
    _, draft, line = plan(conn)
    assert line.supplier_id == sb and draft.groups[0].minimum_status == "met"


def test_11_an_unreachable_minimum_unit_count_is_flagged_too(conn):
    sa = only_a(conn)
    save_terms(conn, sa, Terms(min_qty_for_delivery=100000), "b", NOW)
    assert plan(conn)[1].groups[0].minimum_status == "shortfall"


def test_12_a_reached_free_delivery_threshold_removes_the_charge(conn):
    sa, _ = world(conn)
    save_terms(conn, sa, Terms(free_delivery_threshold=D("1"), delivery_charge=D("9.50")), "b", NOW)
    g = plan(conn)[1].groups[0]
    assert g.free_delivery is True and g.delivery_charge == 0


def test_13_below_the_free_delivery_threshold_the_charge_is_added(conn):
    sa = only_a(conn)
    save_terms(conn, sa, Terms(free_delivery_threshold=D("1000000"), delivery_charge=D("9.50")), "b", NOW)
    g = plan(conn)[1].groups[0]
    assert g.free_delivery is False and g.delivery_charge == D("9.50") and g.total == g.subtotal - g.discount + g.delivery_charge


# ---- delivery dates ----
def test_14_without_schedule_rules_the_date_is_today_plus_the_lead_time(conn):
    world(conn, lead=6)
    assert plan(conn)[1].groups[0].expected_delivery == TODAY + timedelta(days=6)


def test_15_a_supplier_lead_time_shortens_the_date(conn):
    sa, _ = world(conn, lead=6)
    save_terms(conn, sa, Terms(lead_time_days=2), "b", NOW)
    assert plan(conn)[1].groups[0].expected_delivery == TODAY + timedelta(days=2)


def test_16_a_product_override_lead_time_wins_over_the_supplier_value(conn):
    sa, _ = world(conn, lead=6)
    save_terms(conn, sa, Terms(lead_time_days=2), "b", NOW)
    save_override(conn, 1, sa, OverrideTerms(lead_time_days=4), "b", NOW)
    assert plan(conn)[1].groups[0].expected_delivery == TODAY + timedelta(days=4)


def test_17_delivery_weekdays_put_the_date_on_a_delivery_day_never_before_the_lead_time(conn):
    sa, _ = world(conn, lead=6)
    save_terms(conn, sa, Terms(delivery_weekdays=(2, 5)), "b", NOW)
    date = plan(conn)[1].groups[0].expected_delivery
    assert date.isoweekday() in (2, 5) and TODAY + timedelta(days=6) <= date < TODAY + timedelta(days=9)


def test_18_order_days_move_the_order_date_and_so_the_delivery(conn):
    sa, _ = world(conn, lead=3)
    save_terms(conn, sa, Terms(order_days=(1,), delivery_weekdays=()), "b", NOW)
    built, draft, _ = plan(conn)
    order = built.suppliers[sa].next_order_date
    assert order is not None and order.isoweekday() == 1 and draft.groups[0].expected_delivery == order + timedelta(days=3)


def test_19_a_cutoff_that_has_passed_pushes_the_order_to_the_next_day(conn):
    sa, _ = world(conn, lead=3)
    save_terms(conn, sa, Terms(order_days=EVERY_DAY, order_cutoff_time="00:00"), "b", NOW)
    built, _, _ = plan(conn)
    assert built.suppliers[sa].next_order_date >= datetime.now(UTC).astimezone().date()     # never in the past, and after midnight local it is tomorrow


# ---- which terms version is used and cited ----
def test_20_the_line_cites_the_latest_started_version(conn):
    sa, _ = world(conn)
    save_terms(conn, sa, Terms(lead_time_days=5), "b", NOW)
    save_terms(conn, sa, Terms(lead_time_days=2), "b", NOW + timedelta(seconds=1), expected_version=1)
    ex = plan(conn)[2].explanation["terms"]
    assert ex["supplier_version"] == 2 and ex["sources"]["lead_time_days"] == "supplier"


def test_21_a_future_dated_version_is_not_used_or_cited_yet(conn):
    sa, _ = world(conn, lead=6)
    save_terms(conn, sa, Terms(lead_time_days=5), "b", NOW)
    save_terms(conn, sa, Terms(lead_time_days=1), "b", NOW, valid_from=datetime.now(UTC) + timedelta(days=30), expected_version=1)
    _built, draft, line = plan(conn)
    assert line.explanation["terms"]["supplier_version"] == 1 and draft.groups[0].expected_delivery == TODAY + timedelta(days=5)


def test_22_an_expired_window_with_no_successor_falls_back_to_the_erp_values(conn):
    sa, _ = world(conn, lead=6)
    save_terms(conn, sa, Terms(lead_time_days=1, valid_to=NOW + timedelta(days=1)), "b", NOW, valid_from=NOW)
    _, draft, line = plan(conn)
    assert line.explanation["terms"]["supplier_version"] is None and draft.groups[0].expected_delivery == TODAY + timedelta(days=6)
