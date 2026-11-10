"""T028 (FR-020): the supplier's order days, cutoff and delivery weekdays reach the optimizer's inputs, and the group date follows them.

Suppliers with no schedule keep today's meaning (today plus the lead time), so nothing changes for them.
"""

from __future__ import annotations

from datetime import datetime

from conftest import NOW, add_supplier
from proposals.generate import generate
from proposals.inputs import InputsProvider
from terms.schedule import order_date_from
from terms.service import Terms, save_terms
from test_inputs import ELIGIBLE, TODAY, Src, cost, fc, stock, sv

EVERY_DAY = (1, 2, 3, 4, 5, 6, 7)


def build(conn):
    return InputsProvider(Src(stock(sv(1, 10))), Src(fc(v1=ELIGIBLE))).build(conn, TODAY)


def supplier_with(conn, terms: Terms | None):
    sa = add_supplier(conn)
    cost(conn, sa, 10)
    if terms is not None:
        save_terms(conn, sa, terms, "buyer-1", NOW, valid_from=NOW)
    return sa


def test_the_schedule_of_the_terms_in_force_reaches_the_inputs(conn):
    sa = supplier_with(conn, Terms(order_days=EVERY_DAY, delivery_weekdays=(2, 5), lead_time_days=3))
    before = order_date_from(datetime.now().astimezone(), EVERY_DAY, None)
    inp = build(conn)
    after = order_date_from(datetime.now().astimezone(), EVERY_DAY, None)
    t = inp.suppliers[sa]
    assert t.delivery_weekdays == (2, 5)
    assert t.next_order_date in {before, after}                       # every day is an order day, so it is the local date of the build


def test_a_cutoff_alone_is_enough_to_compute_the_order_date(conn):
    sa = supplier_with(conn, Terms(order_cutoff_time="00:00"))        # the cutoff of the day has (almost always) passed: the next day
    assert build(conn).suppliers[sa].next_order_date is not None


def test_a_supplier_without_schedule_rules_keeps_the_old_meaning(conn):
    sa = supplier_with(conn, Terms(lead_time_days=3))
    t = build(conn).suppliers[sa]
    assert (t.next_order_date, t.delivery_weekdays) == (None, ())


def test_a_supplier_without_any_terms_keeps_the_old_meaning(conn):
    sa = supplier_with(conn, None)
    t = build(conn).suppliers[sa]
    assert (t.next_order_date, t.delivery_weekdays) == (None, ())


def test_delivery_weekdays_alone_move_the_group_date_to_a_delivery_day(conn):
    supplier_with(conn, Terms(delivery_weekdays=(2,)))                # Tuesdays only
    draft = generate(build(conn), 10)
    assert draft.groups and all(g.expected_delivery.isoweekday() == 2 for g in draft.groups)
