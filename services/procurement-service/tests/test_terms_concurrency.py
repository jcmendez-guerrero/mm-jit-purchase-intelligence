"""T043: terms use optimistic concurrency; a stale editor gets a conflict that shows the newer version."""

import pytest
from conftest import NOW, add_supplier
from terms.service import Terms, TermsConflict, current_version, save_terms, versions


@pytest.fixture
def sid(conn):
    return add_supplier(conn, 1, "Proveedor Sintético A")


def test_the_first_save_expects_no_existing_version(conn, sid):
    assert current_version(conn, sid) == 0
    assert save_terms(conn, sid, Terms(lead_time_days=3), "b", NOW, expected_version=0) == 1


def test_a_matching_expected_version_is_accepted(conn, sid):
    save_terms(conn, sid, Terms(lead_time_days=3), "b", NOW)
    assert save_terms(conn, sid, Terms(lead_time_days=4), "b", NOW, expected_version=1) == 2


def test_a_stale_expected_version_is_refused_and_reports_the_current_one(conn, sid):
    save_terms(conn, sid, Terms(lead_time_days=3), "b", NOW)
    save_terms(conn, sid, Terms(lead_time_days=4), "other", NOW, expected_version=1)
    with pytest.raises(TermsConflict) as exc:
        save_terms(conn, sid, Terms(lead_time_days=9), "b", NOW, expected_version=1)          # based on the version it read earlier
    assert exc.value.code == "revision_conflict" and exc.value.current_version == 2
    assert len(versions(conn, sid)) == 2                                                  # the stale edit stored nothing


def test_expecting_a_first_save_when_versions_exist_is_a_conflict(conn, sid):
    save_terms(conn, sid, Terms(), "b", NOW)
    with pytest.raises(TermsConflict):
        save_terms(conn, sid, Terms(), "b", NOW, expected_version=0)
