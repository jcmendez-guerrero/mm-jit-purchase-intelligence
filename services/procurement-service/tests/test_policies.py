"""T072: policy range validation, revision conflicts, scopes, budget caps."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from policies.service import (
    PolicyConflict,
    PolicyError,
    PolicyValues,
    effective_weekly_budget,
    history,
    resolve_policy,
    save_budget_cap,
    save_policy,
)

D = Decimal
TODAY = date(2026, 11, 9)


def save(conn, scope="global", key="*", expected=None, **kw):
    return save_policy(conn, scope, key, PolicyValues(**kw), "buyer-1", expected_revision=expected, today=TODAY)


@pytest.mark.parametrize("kw", [
    {"service_level": D("0.49")}, {"service_level": D("1")}, {"service_level": D("1.5")},
    {"safety_stock_units": -1}, {"min_units": -1}, {"max_units": 2_000_000}, {"min_units": 10, "max_units": 5},
    {"replenishment_cadence_days": 0}, {"replenishment_cadence_days": 91}, {},
])
def test_out_of_range_values_are_refused_with_the_range_code(conn, kw):
    with pytest.raises(PolicyError) as e:
        save(conn, **kw)
    assert e.value.code == "policy_out_of_range"


def test_the_boundaries_are_accepted(conn):
    assert save(conn, service_level=D("0.5")) == 1
    assert save(conn, expected=1, service_level=D("0.9999"), min_units=0, max_units=0, replenishment_cadence_days=90) == 2


def test_scope_and_key_must_match(conn):
    for scope, key in (("global", "A"), ("segment", "Z"), ("product", "abc"), ("product", "0"), ("planet", "*")):
        with pytest.raises(PolicyError):
            save(conn, scope, key, service_level=D("0.9"))
    save(conn, "segment", "critical", service_level=D("0.99"))
    save(conn, "product", "123", min_units=2)


def test_floats_are_refused(conn):
    with pytest.raises(TypeError):
        save(conn, service_level=0.9)


def test_a_stale_revision_is_a_conflict_that_names_the_current_one(conn):
    save(conn, service_level=D("0.9"))
    save(conn, expected=1, service_level=D("0.92"))
    with pytest.raises(PolicyConflict) as e:
        save(conn, expected=1, service_level=D("0.93"))
    assert e.value.current_revision == 2 and e.value.code == "revision_conflict"
    with pytest.raises(PolicyConflict):
        save(conn, expected=0, service_level=D("0.93"))


def test_a_policy_cannot_start_in_the_past_and_a_future_start_is_kept_pending(conn):
    with pytest.raises(PolicyError):
        save_policy(conn, "global", "*", PolicyValues(service_level=D("0.9")), "b", valid_from=TODAY - timedelta(days=1), today=TODAY)
    save(conn, service_level=D("0.9"))
    save_policy(conn, "global", "*", PolicyValues(service_level=D("0.97")), "b", valid_from=TODAY + timedelta(days=7), expected_revision=1, today=TODAY)
    assert resolve_policy(conn, 1, (), TODAY).values.service_level == D("0.9")
    assert resolve_policy(conn, 1, (), TODAY + timedelta(days=7)).values.service_level == D("0.97")
    assert [h["revision"] for h in history(conn, "global", "*")] == [1, 2]


def test_two_saves_on_the_same_day_keep_both_in_the_history(conn):
    save(conn, service_level=D("0.9"))
    save(conn, expected=1, service_level=D("0.95"))
    assert resolve_policy(conn, 1, (), TODAY).values.service_level == D("0.95") and len(history(conn, "global", "*")) == 2


def test_the_most_specific_scope_wins_per_field_and_sources_are_reported(conn):
    save(conn, service_level=D("0.9"), min_units=1, replenishment_cadence_days=7)
    save(conn, "segment", "A", service_level=D("0.97"))
    save(conn, "product", "5", min_units=4)
    p = resolve_policy(conn, 5, ("A",), TODAY)
    assert (p.values.service_level, p.values.min_units, p.values.replenishment_cadence_days) == (D("0.97"), 4, 7)
    assert p.sources == {"min_units": "product:5", "service_level": "segment:A", "replenishment_cadence_days": "global:*"}
    assert p.revisions == {"product:5": 1, "segment:A": 1, "global:*": 1}


def test_budget_caps_validate_and_the_weekly_cap_is_the_tighter_of_week_and_month(conn):
    for args in (("year", "global", None, D("1")), ("week", "global", "x", D("1")), ("week", "supplier", None, D("1")), ("week", "global", None, D("-1"))):
        with pytest.raises(PolicyError):
            save_budget_cap(conn, *args, "b", today=TODAY)
    assert effective_weekly_budget(conn, TODAY) is None
    save_budget_cap(conn, "week", "global", None, D("1000"), "b", today=TODAY)
    save_budget_cap(conn, "month", "global", None, D("3000"), "b", today=TODAY)                  # 692.84 a week: tighter
    assert effective_weekly_budget(conn, TODAY) == D("692.84")
