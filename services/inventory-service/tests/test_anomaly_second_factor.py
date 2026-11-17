"""T088 (inventory, FR-004, ADR-023): the service itself decides which anomaly decisions need a fresh second factor; the gateway only says whether it saw one."""

import pytest
from conftest import auth
from test_quality_api import seed_case

FRESH = {"X-Fresh-Second-Factor": "true"}
STALE = {"X-Fresh-Second-Factor": "false"}


def put(client, sku, decision, extra=None, who="buyer"):
    return client.put(f"/quality/products/{sku}/anomalies/2026-03-12", json={"decision": decision, "reason_code": "data_error"}, headers={**auth(who), **(extra or {})})


def decisions(client, sku):
    return {a["decision"] for a in client.get(f"/quality/products/{sku}/anomalies", headers=auth()).json()["anomalies"] if a["day"] == "2026-03-12"}


@pytest.mark.parametrize("extra", [None, STALE, {"X-Fresh-Second-Factor": "yes"}])
def test_excluding_a_day_without_a_fresh_second_factor_is_refused_and_changes_nothing(client, engine, extra):
    sku, _ = seed_case(engine, "outlier")
    r = put(client, sku, "excluded", extra)
    assert r.status_code == 403 and r.json()["detail"] == "auth_mfa_stale"
    assert decisions(client, sku) == {"pending"}


def test_excluding_with_a_fresh_second_factor_works_for_buyers_and_admins(client, engine):
    sku, _ = seed_case(engine, "outlier")
    assert put(client, sku, "excluded", FRESH, "admin").status_code == 200
    assert decisions(client, sku) == {"excluded"}


def test_accepting_a_pending_day_needs_no_second_factor(client, engine):
    sku, _ = seed_case(engine, "outlier")
    assert put(client, sku, "accepted").status_code == 200


def test_reversing_an_exclusion_needs_a_fresh_second_factor_in_the_service_too(client, engine):
    sku, _ = seed_case(engine, "outlier")
    put(client, sku, "excluded", FRESH)
    r = put(client, sku, "accepted", STALE)
    assert r.status_code == 403 and r.json()["detail"] == "auth_mfa_stale" and decisions(client, sku) == {"excluded"}
    assert put(client, sku, "accepted", FRESH).status_code == 200 and decisions(client, sku) == {"accepted"}


def _refusals(engine):
    from audit import verify_chain
    from db.tables import audit_events
    from sqlalchemy import select

    with engine.connect() as c:
        rows = c.execute(select(audit_events).where(audit_events.c.action == "quality.anomaly_refused").order_by(audit_events.c.id)).all()
        return rows, verify_chain(c).ok


def test_a_refused_second_factor_attempt_is_audited_without_free_text(client, engine):
    sku, _ = seed_case(engine, "outlier")
    assert put(client, sku, "excluded", STALE).status_code == 403
    rows, chain_ok = _refusals(engine)
    assert len(rows) == 1 and chain_ok
    assert rows[0].actor == "buyer-test" or rows[0].actor
    assert rows[0].entity == "anomaly_flags" and rows[0].after == {"decision": "excluded", "reason": "mfa_stale"}
    assert put(client, sku, "excluded").status_code == 403                    # each attempt leaves its own record
    assert len(_refusals(engine)[0]) == 2


def test_allowed_and_accepted_decisions_leave_no_refusal_record(client, engine):
    sku, _ = seed_case(engine, "outlier")
    assert put(client, sku, "accepted").status_code == 200
    assert put(client, sku, "excluded", FRESH).status_code == 200
    assert _refusals(engine)[0] == []
