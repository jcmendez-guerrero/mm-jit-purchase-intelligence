"""T042: field precedence (ADR-019): the most specific approved local value wins, ERP facts stay ERP facts, conflicts are shown."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from conftest import NOW, add_supplier
from terms.overrides import OverrideTerms, TermsOverrideConflict, current_override, override_history, save_override
from terms.resolve import resolve_effective
from terms.service import Discount, Terms, TermsError, save_terms

D = Decimal
VID = 9001
ERP = {"source": "siweb_product_supplier", "lead_time_days": 4, "pack_size": 6, "min_order_qty": 0}


@pytest.fixture
def sid(conn):
    s = add_supplier(conn, 1, "Proveedor Sintético A")
    save_terms(conn, s, Terms(lead_time_days=3, preferred=True, discounts=(Discount("percent", "order_value", D("300"), D("2")),), payment_terms_days=30), "b", NOW)
    return s


def test_supplier_terms_apply_when_there_is_no_override(conn, sid):
    e = resolve_effective(conn, sid, VID, NOW)
    assert (e.lead_time_days, e.preferred, e.payment_terms_days) == (3, True, 30)
    assert e.sources["lead_time_days"] == "supplier" and e.override_version is None and e.supplier_version == 1


def test_a_product_override_wins_for_that_product_only(conn, sid):
    save_override(conn, VID, sid, OverrideTerms(lead_time_days=5, pack_multiple=12), "buyer-1", NOW)
    e, other = resolve_effective(conn, sid, VID, NOW), resolve_effective(conn, sid, 9002, NOW)
    assert (e.lead_time_days, e.pack_multiple, e.sources["lead_time_days"], e.sources["pack_multiple"]) == (5, 12, "override", "override")
    assert e.preferred is True and e.sources["preferred"] == "supplier"           # fields the override leaves empty are inherited
    assert other.lead_time_days == 3 and other.pack_multiple is None


def test_the_override_can_demote_preference_and_discounts_stay_a_supplier_level_term(conn, sid):
    save_override(conn, VID, sid, OverrideTerms(preferred=False), "b", NOW)
    e = resolve_effective(conn, sid, VID, NOW)
    assert e.preferred is False and e.sources["preferred"] == "override"
    assert e.discounts == (Discount("percent", "order_value", D("300"), D("2")),) and e.sources["discounts"] == "supplier"


def test_cost_version_values_fill_in_when_no_local_value_exists(conn, sid):
    e = resolve_effective(conn, sid, VID, NOW, erp={**ERP, "source": "manual"})
    assert (e.pack_multiple, e.min_qty_units, e.sources["pack_multiple"]) == (6, 0, "cost")
    assert e.lead_time_days == 3 and e.sources["lead_time_days"] == "supplier"             # approved local terms beat the cost record's lead time


def test_with_nothing_anywhere_a_flagged_default_is_used(conn):
    s = add_supplier(conn, 2, "Sin condiciones")
    e = resolve_effective(conn, s, VID, NOW)
    assert e.lead_time_days == 7 and e.sources["lead_time_days"] == "default" and "no_supplier_terms" in e.flags


def test_a_local_value_that_differs_from_an_erp_value_is_reported_as_a_conflict_not_hidden(conn, sid):
    save_override(conn, VID, sid, OverrideTerms(lead_time_days=5, pack_multiple=12), "b", NOW)
    e = resolve_effective(conn, sid, VID, NOW, erp=ERP)
    assert e.lead_time_days == 5 and e.pack_multiple == 12                                  # the approved local value wins ...
    assert {(c["field"], c["erp_value"], c["local_value"], c["winner"]) for c in e.conflicts} == {
        ("lead_time_days", 4, 5, "local"), ("pack_multiple", 6, 12, "local")}                # ... and the disagreement is visible


def test_equal_values_and_non_erp_sources_are_not_conflicts(conn, sid):
    save_override(conn, VID, sid, OverrideTerms(pack_multiple=6), "b", NOW)
    assert resolve_effective(conn, sid, VID, NOW, erp={**ERP, "lead_time_days": 3}).conflicts == ()       # supplier lead time 3 equals the ERP's
    save_override(conn, VID, sid, OverrideTerms(pack_multiple=12), "b", NOW)
    assert resolve_effective(conn, sid, VID, NOW, erp={**ERP, "source": "manual"}).conflicts == ()


def test_a_disabled_supplier_stays_disabled_and_an_override_can_only_add_a_disable(conn, sid):
    other = add_supplier(conn, 2, "B")
    save_terms(conn, other, Terms(disabled=True), "b", NOW)
    save_override(conn, VID, other, OverrideTerms(disabled=False), "b", NOW)
    assert resolve_effective(conn, other, VID, NOW).disabled is True                       # an override cannot re-enable a disabled supplier
    save_override(conn, VID, sid, OverrideTerms(disabled=True), "b", NOW)
    assert resolve_effective(conn, sid, VID, NOW).disabled is True and resolve_effective(conn, sid, 9002, NOW).disabled is False


def test_an_override_outside_its_validity_window_is_ignored(conn, sid):
    save_override(conn, VID, sid, OverrideTerms(lead_time_days=9), "b", NOW, valid_from=datetime(2026, 1, 1, tzinfo=UTC), valid_to=datetime(2026, 6, 1, tzinfo=UTC))
    assert resolve_effective(conn, sid, VID, NOW).lead_time_days == 3
    assert resolve_effective(conn, sid, VID, datetime(2026, 3, 1, tzinfo=UTC)).lead_time_days == 9


def test_override_versions_are_appended_and_audited(conn, sid):
    assert save_override(conn, VID, sid, OverrideTerms(lead_time_days=5), "buyer-1", NOW, reason="transportista nuevo") == 1
    assert save_override(conn, VID, sid, OverrideTerms(lead_time_days=6), "buyer-2", NOW, expected_version=1) == 2
    assert current_override(conn, VID, sid, NOW).lead_time_days == 6
    assert [(v["version"], v["changed_by"]) for v in override_history(conn, VID, sid)] == [(1, "buyer-1"), (2, "buyer-2")]
    with pytest.raises(TermsOverrideConflict) as exc:
        save_override(conn, VID, sid, OverrideTerms(lead_time_days=7), "buyer-3", NOW, expected_version=1)
    assert exc.value.code == "revision_conflict" and exc.value.current_version == 2


@pytest.mark.parametrize("bad", [OverrideTerms(pack_multiple=0), OverrideTerms(min_qty_units=-1), OverrideTerms(lead_time_days=400), OverrideTerms(reliability=101)])
def test_override_values_are_validated_like_supplier_terms(conn, sid, bad):
    with pytest.raises(TermsError) as exc:
        save_override(conn, VID, sid, bad, "b", NOW)
    assert exc.value.code in {"terms_invalid_value", "terms_negative_amount"} and override_history(conn, VID, sid) == []
