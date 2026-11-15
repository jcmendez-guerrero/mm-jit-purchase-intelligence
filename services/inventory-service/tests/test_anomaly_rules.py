"""T016: deterministic anomaly rules; the original value is kept and nothing is corrected (FR-004, research R2)."""

from datetime import date, timedelta

import quality_fixtures as qf
from quality.anomalies import MAD_ABOVE, MIN_NONZERO, detect

START = date(2026, 1, 1)


def series(values):
    return [START + timedelta(days=i) for i in range(len(values))], list(values)


def rules(found):
    return {(a.day.isoformat(), a.rule_id) for a in found}


def test_the_synthetic_outlier_is_flagged_by_both_outlier_rules_with_its_original_value():
    s = qf.build_series("outlier")
    days, demand = series(s["demand"])
    found = detect(days, demand)
    assert {(a.rule_id, a.original_value) for a in found if a.day == days[qf.OUTLIER_DAY]} == {("mad_outlier", qf.OUTLIER_VALUE), ("p95_cap", qf.OUTLIER_VALUE)}
    assert all(a.day == days[qf.OUTLIER_DAY] for a in found)          # nothing else is flagged
    assert demand[qf.OUTLIER_DAY] == qf.OUTLIER_VALUE                 # the input is never changed


def test_a_smooth_series_has_no_anomalies():
    days, demand = series(qf.build_series("smooth")["demand"])
    assert detect(days, demand) == []


def test_flat_series_is_not_flagged_by_a_zero_spread():
    days, demand = series([3] * 60 + [4] + [3] * 20)       # MAD is zero; the floor keeps a one-unit step from being an outlier
    assert detect(days, demand) == []


def test_too_little_history_in_the_window_flags_nothing_by_the_statistical_rules():
    values = [2] * (MIN_NONZERO - 1) + [500]
    days, demand = series(values)
    assert detect(days, demand) == []


def test_negative_quantity_is_always_flagged_even_without_history():
    days, demand = series([2, -3, 2])
    assert rules(detect(days, demand)) == {("2026-01-02", "negative_qty")}


def test_censored_days_are_never_flagged():
    s = qf.build_series("stockout")
    days, demand = series(s["demand"])
    assert detect(days, demand, s["censored"]) == []


def test_a_large_value_outside_the_trailing_window_does_not_hide_a_later_one():
    base = [3, 4] * 60
    days, demand = series([*base, 80, *base, 90])
    flagged = {a.original_value for a in detect(days, demand)}
    assert 80 in flagged and 90 in flagged


def test_results_are_deterministic_and_the_threshold_constant_is_five():
    days, demand = series(qf.build_series("outlier")["demand"])
    assert detect(days, demand) == detect(days, demand) and MAD_ABOVE == 5
