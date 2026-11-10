"""Feature 011 (T011-T013, T019, T024): overlap refusal, budget-cap revision checks, SKU resolution and the effective-policy view."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from db.tables import product_refs
from policies.service import (
    PolicyConflict,
    PolicyError,
    PolicyValues,
    budget_cap_revision,
    effective_view,
    save_budget_cap,
    save_policy,
    sku_for_variant,
    variant_for_sku,
)
from sqlalchemy import insert

D = Decimal
TODAY = date(2026, 11, 9)


def save(conn, scope="global", key="*", expected=None, valid_from=None, **kw):
    return save_policy(conn, scope, key, PolicyValues(**kw), "buyer-1", expected_revision=expected, valid_from=valid_from, today=TODAY)


def test_a_save_dated_before_a_scheduled_revision_is_refused_as_overlap(conn):
    save(conn, valid_from=TODAY + timedelta(days=10), service_level=D("0.95"))
    with pytest.raises(PolicyError) as e:
        save(conn, expected=1, valid_from=TODAY, service_level=D("0.9"))
    assert e.value.code == "policy_overlap"


def test_a_save_on_or_after_the_scheduled_date_is_accepted(conn):
    save(conn, valid_from=TODAY + timedelta(days=10), service_level=D("0.95"))
    assert save(conn, expected=1, valid_from=TODAY + timedelta(days=10), service_level=D("0.9")) == 2
    assert save(conn, expected=2, valid_from=TODAY + timedelta(days=20), service_level=D("0.92")) == 3


def test_overlap_is_per_scope_and_key(conn):
    save(conn, valid_from=TODAY + timedelta(days=10), service_level=D("0.95"))
    assert save(conn, "segment", "A", valid_from=TODAY, service_level=D("0.9")) == 1


def cap(conn, amount="100", expected=None, valid_from=None, scope="global", scope_key=None):
    return save_budget_cap(conn, "week", scope, scope_key, D(amount), "buyer-1", valid_from=valid_from, today=TODAY, expected_revision=expected)


def test_a_stale_budget_cap_save_is_a_conflict_and_stores_nothing(conn):
    cap(conn, "100", expected=0)
    with pytest.raises(PolicyConflict) as e:
        cap(conn, "200", expected=0)
    assert e.value.current_revision == 1
    assert budget_cap_revision(conn, "week", "global", None) == 1


def test_a_budget_cap_save_with_the_current_revision_succeeds(conn):
    cap(conn, "100", expected=0)
    cap(conn, "200", expected=1)
    assert budget_cap_revision(conn, "week", "global", None) == 2


def test_a_budget_cap_dated_before_a_scheduled_one_is_refused(conn):
    cap(conn, "100", expected=0, valid_from=TODAY + timedelta(days=7))
    with pytest.raises(PolicyError) as e:
        cap(conn, "200", expected=1, valid_from=TODAY)
    assert e.value.code == "policy_overlap"


def add_ref(conn, variant_id, sku):
    conn.execute(insert(product_refs).values(variant_id=variant_id, product_id=variant_id, sku=sku, name="Producto sintético"))


def test_sku_resolves_to_its_variant_ignoring_case_and_spaces(conn):
    add_ref(conn, 11, "SYN-0001")
    assert variant_for_sku(conn, " syn-0001 ") == 11
    assert sku_for_variant(conn, 11) == "SYN-0001"


def test_unknown_and_ambiguous_skus_are_refused(conn):
    add_ref(conn, 11, "SYN-0002")
    add_ref(conn, 12, "syn-0002 ")
    with pytest.raises(PolicyError) as e:
        variant_for_sku(conn, "SYN-0002")
    assert e.value.code == "sku_ambiguous"
    with pytest.raises(PolicyError) as e2:
        variant_for_sku(conn, "SYN-9999")
    assert e2.value.code == "sku_unknown"
    with pytest.raises(PolicyError):
        variant_for_sku(conn, "  ")


def test_the_effective_view_names_the_source_of_each_rule(conn):
    save(conn, service_level=D("0.9"), min_units=1)
    save(conn, "segment", "A", service_level=D("0.97"))
    save(conn, "product", "5", min_units=4)
    view = effective_view(conn, 5, ("A",), TODAY)
    assert view["service_level"]["source"] == "segment" and view["service_level"]["value"] == "0.9700"
    assert view["min_units"]["source"] == "product" and view["min_units"]["key"] == "5" and view["min_units"]["revision"] == 1
    assert view["max_units"] == {"value": None, "source": "default", "key": None, "revision": None, "valid_from": None}


def test_a_global_only_product_shows_global_as_the_source(conn):
    save(conn, service_level=D("0.9"))
    assert effective_view(conn, 7, (), TODAY)["service_level"]["source"] == "global"
