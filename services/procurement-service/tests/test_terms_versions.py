"""T041: terms are effective-dated, append-only versions; the version valid on a date is the one used; history is complete."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from conftest import NOW, add_supplier
from db.tables import supplier_terms
from sqlalchemy import select
from terms.service import Terms, TermsError, current_terms, history, save_terms, versions

D = Decimal
JAN, JUN, DEC = (datetime(2026, m, 1, tzinfo=UTC) for m in (1, 6, 12))


@pytest.fixture
def sid(conn):
    return add_supplier(conn, 1, "Proveedor Sintético A")


def test_every_save_is_a_new_numbered_version_and_old_rows_never_change(conn, sid):
    assert save_terms(conn, sid, Terms(lead_time_days=3), "buyer-1", JAN, valid_from=JAN) == 1
    first = [dict(r._mapping) for r in conn.execute(select(supplier_terms)).all()]
    assert save_terms(conn, sid, Terms(lead_time_days=5), "buyer-2", JUN, valid_from=JUN) == 2
    rows = conn.execute(select(supplier_terms).order_by(supplier_terms.c.version)).all()
    assert [r.version for r in rows] == [1, 2] and dict(rows[0]._mapping) == first[0]


def test_the_version_valid_on_the_date_is_used(conn, sid):
    save_terms(conn, sid, Terms(lead_time_days=3), "b", JAN, valid_from=JAN)
    save_terms(conn, sid, Terms(lead_time_days=5), "b", JUN, valid_from=JUN)
    assert current_terms(conn, sid, JAN - timedelta(days=1)) is None
    assert current_terms(conn, sid, JAN + timedelta(days=10)).lead_time_days == 3
    assert current_terms(conn, sid, JUN).lead_time_days == 5
    assert current_terms(conn, sid, DEC).lead_time_days == 5


def test_a_future_dated_version_is_not_used_before_its_date(conn, sid):
    save_terms(conn, sid, Terms(lead_time_days=3), "b", JAN, valid_from=JAN)
    save_terms(conn, sid, Terms(lead_time_days=9), "b", JAN, valid_from=DEC)          # planned change for December
    assert current_terms(conn, sid, NOW).lead_time_days == 3
    assert current_terms(conn, sid, DEC + timedelta(days=1)).lead_time_days == 9


def test_an_expired_window_with_no_successor_yields_no_terms(conn, sid):
    save_terms(conn, sid, Terms(lead_time_days=3, valid_to=JUN), "b", JAN, valid_from=JAN)
    assert current_terms(conn, sid, JAN + timedelta(days=30)).lead_time_days == 3
    assert current_terms(conn, sid, JUN + timedelta(days=1)) is None


def test_a_new_version_starting_inside_an_explicit_window_is_an_overlap(conn, sid):
    save_terms(conn, sid, Terms(lead_time_days=3, valid_to=datetime(2026, 6, 30, tzinfo=UTC)), "b", JAN, valid_from=JAN)
    with pytest.raises(TermsError) as exc:
        save_terms(conn, sid, Terms(lead_time_days=5), "b", JAN, valid_from=JUN)
    assert exc.value.code == "terms_window_overlap" and len(versions(conn, sid)) == 1


def test_a_new_explicit_window_may_not_swallow_a_later_version(conn, sid):
    save_terms(conn, sid, Terms(lead_time_days=3), "b", JAN, valid_from=JAN)
    save_terms(conn, sid, Terms(lead_time_days=9), "b", JAN, valid_from=DEC)
    with pytest.raises(TermsError) as exc:
        save_terms(conn, sid, Terms(lead_time_days=4, valid_to=datetime(2027, 3, 1, tzinfo=UTC)), "b", JAN, valid_from=JUN)
    assert exc.value.code == "terms_window_overlap"


def test_adjacent_windows_do_not_overlap(conn, sid):
    save_terms(conn, sid, Terms(lead_time_days=3, valid_to=JUN), "b", JAN, valid_from=JAN)
    assert save_terms(conn, sid, Terms(lead_time_days=5), "b", JAN, valid_from=JUN) == 2


def test_history_lists_every_version_with_who_why_and_source(conn, sid):
    save_terms(conn, sid, Terms(lead_time_days=3), "buyer-1", JAN, valid_from=JAN, source="erp", reason="alta inicial")
    save_terms(conn, sid, Terms(lead_time_days=5), "buyer-2", JUN, valid_from=JUN, reason="cambio de transportista")
    h = history(conn, sid)
    assert [(v["version"], v["changed_by"], v["source"], v["reason"]) for v in h] == [
        (1, "buyer-1", "erp", "alta inicial"), (2, "buyer-2", "manual", "cambio de transportista")]
    assert h[1]["terms"].lead_time_days == 5 and h[1]["valid_from"] == JUN


def test_two_versions_starting_on_the_same_day_the_later_saved_wins_and_the_other_is_superseded(conn, sid):
    from terms.service import version_statuses

    save_terms(conn, sid, Terms(lead_time_days=3), "b", JAN, valid_from=JUN)
    save_terms(conn, sid, Terms(lead_time_days=8), "b", JAN, valid_from=JUN)
    later = JUN + timedelta(days=1)
    assert current_terms(conn, sid, later).lead_time_days == 8
    assert version_statuses(conn, sid, later) == {1: "superseded", 2: "in_force"}


def test_each_version_is_in_force_planned_superseded_or_expired(conn, sid):
    from terms.service import version_statuses

    save_terms(conn, sid, Terms(lead_time_days=3), "b", JAN, valid_from=JAN)
    save_terms(conn, sid, Terms(lead_time_days=5), "b", JAN, valid_from=JUN)
    save_terms(conn, sid, Terms(lead_time_days=9), "b", JAN, valid_from=DEC)
    assert version_statuses(conn, sid, JUN + timedelta(days=10)) == {1: "superseded", 2: "in_force", 3: "planned"}
    assert version_statuses(conn, sid, JAN - timedelta(days=1)) == {1: "planned", 2: "planned", 3: "planned"}
    assert version_statuses(conn, sid, DEC + timedelta(days=1)) == {1: "superseded", 2: "superseded", 3: "in_force"}


def test_a_window_that_ended_with_no_successor_is_expired(conn, sid):
    from terms.service import version_statuses

    save_terms(conn, sid, Terms(lead_time_days=3, valid_to=JUN), "b", JAN, valid_from=JAN)
    assert version_statuses(conn, sid, JAN + timedelta(days=5)) == {1: "in_force"}
    assert version_statuses(conn, sid, DEC) == {1: "expired"}


def test_every_save_is_audited_in_the_hash_chain(conn, sid):
    from audit.chain import verify_chain
    from db.tables import audit_events

    save_terms(conn, sid, Terms(lead_time_days=3), "buyer-1", JAN, valid_from=JAN)
    ev = conn.execute(select(audit_events).where(audit_events.c.action == "terms.saved")).one()
    assert ev.actor == "buyer-1" and ev.entity_id == sid and ev.after["lead_time_days"] == 3 and verify_chain(conn).ok
