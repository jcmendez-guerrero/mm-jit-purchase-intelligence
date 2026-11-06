"""T040: supplier terms validation - every invalid input is refused with a specific stable code and nothing is stored."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from conftest import NOW, add_supplier
from terms.service import Discount, Terms, TermsError, current_terms, save_terms, versions

D = Decimal


@pytest.fixture
def sid(conn):
    return add_supplier(conn, 1, "Proveedor Sintético A")


def refused(conn, sid, code, **fields):
    with pytest.raises(TermsError) as exc:
        save_terms(conn, sid, Terms(**fields), "buyer-1", NOW)
    assert exc.value.code == code, (fields, exc.value.code)
    assert versions(conn, sid) == []                                    # nothing stored on a refusal


@pytest.mark.parametrize("field", ["min_order_value", "free_delivery_threshold", "delivery_charge"])
def test_negative_money_is_refused(conn, sid, field):
    refused(conn, sid, "terms_negative_amount", **{field: D("-0.01")})


def test_negative_quantity_and_discount_amounts_are_refused(conn, sid):
    refused(conn, sid, "terms_negative_amount", min_qty_for_delivery=-1)
    refused(conn, sid, "terms_negative_amount", discounts=(Discount("amount", "order_value", D("100"), D("-5")),))
    refused(conn, sid, "terms_negative_amount", discounts=(Discount("amount", "order_value", D("-1"), D("5")),))


def test_free_shipping_threshold_below_the_minimum_order_is_refused(conn, sid):
    refused(conn, sid, "terms_threshold_below_minimum", min_order_value=D("200"), free_delivery_threshold=D("100"))


@pytest.mark.parametrize("days", [(0,), (8,), (1, 1), (-1, 3)])
def test_impossible_or_repeated_weekdays_are_refused(conn, sid, days):
    refused(conn, sid, "terms_invalid_weekday", order_days=days)
    refused(conn, sid, "terms_invalid_weekday", delivery_weekdays=days)


@pytest.mark.parametrize(("field", "value"), [("lead_time_days", -1), ("lead_time_days", 366), ("payment_terms_days", -1), ("reliability", 101),
                                              ("reliability", -1), ("order_cutoff_time", "25:00"), ("order_cutoff_time", "9:5"), ("order_cutoff_time", "12:60")])
def test_out_of_range_values_are_refused(conn, sid, field, value):
    refused(conn, sid, "terms_invalid_value", **{field: value})


@pytest.mark.parametrize("bad", [Discount("percent", "order_value", D("100"), D("0")), Discount("percent", "order_value", D("100"), D("101")),
                                 Discount("bogus", "order_value", D("100"), D("5")), Discount("percent", "weight", D("100"), D("5"))])
def test_malformed_discounts_are_refused(conn, sid, bad):
    refused(conn, sid, "terms_invalid_value", discounts=(bad,))


def test_too_many_discount_tiers_are_refused(conn, sid):
    tiers = tuple(Discount("percent", "order_value", D(100 * i), D("1")) for i in range(1, 7))
    refused(conn, sid, "terms_invalid_value", discounts=tiers)


def test_the_validity_window_must_end_after_it_starts(conn, sid):
    with pytest.raises(TermsError) as exc:
        save_terms(conn, sid, Terms(valid_to=datetime(2026, 1, 1, tzinfo=UTC)), "buyer-1", NOW)
    assert exc.value.code == "terms_window_overlap" and versions(conn, sid) == []


def test_an_unknown_supplier_is_refused(conn):
    with pytest.raises(TermsError) as exc:
        save_terms(conn, "no-such-supplier", Terms(), "buyer-1", NOW)
    assert exc.value.code == "invalid_terms"


def test_a_complete_valid_set_is_stored_and_read_back(conn, sid):
    full = Terms(min_order_value=D("150.00"), min_qty_for_delivery=12, free_delivery_threshold=D("300.00"), delivery_charge=D("9.90"), order_days=(1, 4),
                 delivery_schedule="martes y viernes", lead_time_days=3, order_cutoff_time="13:30", delivery_weekdays=(2, 5),
                 discounts=(Discount("percent", "order_value", D("500"), D("3")), Discount("amount", "order_units", D("100"), D("15"))),
                 payment_terms_days=30, preferred=True, reliability=92)
    assert save_terms(conn, sid, full, "buyer-1", NOW) == 1
    back = current_terms(conn, sid, NOW)
    assert back == full
