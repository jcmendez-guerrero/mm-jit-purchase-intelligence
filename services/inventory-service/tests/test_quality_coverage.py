"""T015: historical coverage and gap days (FR-002)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from quality.coverage import coverage

START = date(2026, 1, 1)


def days(*offsets):
    return [START + timedelta(days=o) for o in offsets]


def test_full_coverage_has_no_gaps():
    c = coverage(days(*range(10)), START, START + timedelta(days=9))
    assert (c.days_in_period, c.days_with_data, c.ratio, c.gaps) == (10, 10, Decimal("1.000000"), [])


def test_gap_days_are_listed_as_ranges():
    # 90-day period, 12 days without data: 5 + 7 consecutive days
    present = [d for d in range(90) if d not in (10, 11, 12, 13, 14, 40, 41, 42, 43, 44, 45, 46)]
    c = coverage(days(*present), START, START + timedelta(days=89))
    assert c.days_in_period == 90 and c.days_with_data == 78
    assert c.gaps == [(START + timedelta(days=10), START + timedelta(days=14)), (START + timedelta(days=40), START + timedelta(days=46))]
    assert c.ratio == Decimal("0.866667")


def test_days_outside_the_period_and_duplicates_are_ignored():
    c = coverage(days(-3, 0, 0, 1, 20), START, START + timedelta(days=4))
    assert (c.days_with_data, c.days_in_period) == (2, 5)
    assert c.gaps == [(START + timedelta(days=2), START + timedelta(days=4))]


def test_no_data_is_one_big_gap_and_a_one_day_period_works():
    c = coverage([], START, START + timedelta(days=2))
    assert c.ratio == Decimal("0.000000") and c.gaps == [(START, START + timedelta(days=2))]
    assert coverage(days(0), START, START).ratio == Decimal("1.000000")


def test_an_empty_period_is_rejected():
    with pytest.raises(ValueError):
        coverage([], START + timedelta(days=1), START)
