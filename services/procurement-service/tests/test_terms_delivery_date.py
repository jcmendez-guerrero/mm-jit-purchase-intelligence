"""T025 (FR-020, US5-2): the expected delivery date follows the supplier's order days, order cutoff, lead time and delivery weekdays.

2026-11-09 is a Monday (the builders' "today"). Cutoffs are local time (Europe/Madrid); a time exactly at the cutoff still counts as before it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from builders import flat_forecast, inputs, offer, variant
from proposals.generate import RULE_VERSIONS, generate
from proposals.model import SupplierTermsIn, inputs_hash
from terms.schedule import delivery_date, next_order_date, order_date_from

MON, TUE, THU, FRI = date(2026, 11, 9), date(2026, 11, 10), date(2026, 11, 12), date(2026, 11, 13)


def at(day: date, hh: int, mm: int = 0) -> datetime:
    """A local (Madrid) moment on ``day``; only its wall-clock date and time are read."""
    return datetime(day.year, day.month, day.day, hh, mm, tzinfo=ZoneInfo("Europe/Madrid"))


@pytest.mark.parametrize(("placed", "order_days", "cutoff", "expected"), [
    (at(MON, 10), (), None, MON),                                    # no rules: any day, all day
    (at(MON, 10), (1, 4), None, MON),                                # Monday is an order day
    (at(MON, 13, 30), (1, 4), "13:30", MON),                         # exactly at the cutoff still counts
    (at(MON, 13, 31), (1, 4), "13:30", THU),                         # a minute later waits for Thursday
    (at(TUE, 9), (1, 4), "13:30", THU),                              # Tuesday is not an order day
    (at(TUE, 9), (1,), None, date(2026, 11, 16)),                    # next Monday
    (at(MON, 18), (), "13:30", TUE),                                 # every day is an order day, but today's cutoff has passed
    (at(MON, 9), (7,), None, date(2026, 11, 15)),                    # Sunday
    (at(THU, 14), (4,), "13:30", date(2026, 11, 19)),                # the same weekday next week
])
def test_the_next_order_date(placed, order_days, cutoff, expected):
    assert next_order_date(placed, order_days, cutoff) == expected


@pytest.mark.parametrize(("order", "lead", "weekdays", "expected"), [
    (MON, 3, (), THU),                                               # no weekday rule: order date plus lead time
    (MON, 3, (2, 5), FRI),                                           # Thursday is not a delivery day: Friday
    (TUE, 0, (1,), date(2026, 11, 16)),                              # the next Monday
    (MON, 2, (2,), date(2026, 11, 17)),                              # Monday + 2 = Wednesday; the next Tuesday is the 17th
    (MON, 5, (2, 5), date(2026, 11, 17)),                            # Saturday lands on the next Tuesday
])
def test_the_delivery_date(order, lead, weekdays, expected):
    assert delivery_date(order, lead, weekdays) == expected


def test_a_date_that_already_falls_on_a_delivery_day_is_kept():
    assert delivery_date(MON, 2, (3,)) == date(2026, 11, 11)          # Monday + 2 = Wednesday, a delivery day


def test_the_cutoff_is_read_in_madrid_time_not_utc():
    before = datetime(2026, 11, 10, 12, 29, tzinfo=UTC)               # 13:29 in Madrid (UTC+1 in November)
    after = datetime(2026, 11, 10, 12, 31, tzinfo=UTC)                # 13:31
    assert order_date_from(before, (), "13:30") == TUE
    assert order_date_from(after, (), "13:30") == date(2026, 11, 11)


def one_variant(lead=4, vid=1):
    return variant(vid, [offer("A", "1.00", pack=6, lead=lead)], flat_forecast(1.0))


def test_a_group_without_schedule_rules_keeps_today_plus_lead_time():
    draft = generate(inputs([one_variant(lead=4)], [SupplierTermsIn("A")]), 10)
    assert draft.groups[0].expected_delivery == date(2026, 11, 13)


def test_a_group_uses_the_next_order_date_and_the_delivery_weekdays():
    t = SupplierTermsIn("A", next_order_date=THU, delivery_weekdays=(2, 5))
    draft = generate(inputs([one_variant(lead=3)], [t]), 10)
    assert draft.groups[0].expected_delivery == date(2026, 11, 17)     # ordered Thursday + 3 = Sunday, the next delivery day is Tuesday


def test_the_longest_lead_time_among_the_lines_of_a_supplier_sets_the_group_date():
    t = SupplierTermsIn("A", next_order_date=MON)
    draft = generate(inputs([one_variant(lead=2, vid=1), one_variant(lead=6, vid=2)], [t]), 10)
    assert draft.groups[0].expected_delivery == date(2026, 11, 15)


def test_every_line_explanation_shows_the_expected_delivery_date_of_its_supplier():
    t = SupplierTermsIn("A", next_order_date=THU, delivery_weekdays=(2, 5))
    draft = generate(inputs([one_variant(lead=3, vid=1), one_variant(lead=6, vid=2)], [t]), 10)
    group_date = draft.groups[0].expected_delivery
    assert all(ln.explanation["terms"]["expected_delivery_date"] == group_date.isoformat() for ln in draft.lines) and len(draft.lines) == 2


def test_the_precomputed_order_date_is_part_of_the_inputs_hash():
    base = inputs([one_variant()], [SupplierTermsIn("A", next_order_date=MON)])
    other = inputs([one_variant()], [SupplierTermsIn("A", next_order_date=THU)])
    assert inputs_hash(base, RULE_VERSIONS) != inputs_hash(other, RULE_VERSIONS)
