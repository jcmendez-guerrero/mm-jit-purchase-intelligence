"""Feature 011 inventory side (T020, T038): stale saves, the segments and audit reads the gateway calls, and the rule versions the forecast records."""

from datetime import UTC, datetime

from conftest import auth
from db.tables import product_segments
from sqlalchemy import insert
from test_demand_rules import BODY, seed

IF1 = {"If-Match": '"1"'}


def test_a_toggle_without_a_revision_is_428_and_a_stale_one_is_412_with_the_current_revision(client, engine):
    seed(engine)
    xid = client.post("/demand-rules/exclusions", json=BODY, headers=auth("buyer")).json()["id"]
    assert client.put(f"/demand-rules/exclusions/{xid}", json={"active": False}, headers=auth("buyer")).status_code == 428
    assert client.put(f"/demand-rules/exclusions/{xid}", json={"active": False}, headers={**auth("buyer"), **IF1}).status_code == 200
    stale = client.put(f"/demand-rules/exclusions/{xid}", json={"active": True}, headers={**auth("buyer"), **IF1})
    assert stale.status_code == 412 and stale.json() == {"detail": "revision_conflict", "current_version": 2}


def test_a_toggle_that_loses_the_race_changes_nothing_and_is_a_conflict(engine):
    """T058: two toggles read revision 1; only the first update matches."""
    from datetime import date

    from db.tables import demand_exclusions
    from projections.rules import RuleConflict, add_exclusion, exclusion_revision, set_exclusion_active
    from sqlalchemy import update

    with engine.begin() as c:
        xid = add_exclusion(c, None, date(2026, 10, 3), date(2026, 10, 3), "promotion", "buyer-1", now=datetime(2026, 10, 10, tzinfo=UTC))
    with engine.begin() as c:
        real = c.execute

        def racing(stmt, *a, **k):          # another writer toggles between this one's read and write
            if getattr(stmt, "is_update", False) and not getattr(racing, "done", False):
                racing.done = True
                real(update(demand_exclusions).where(demand_exclusions.c.id == xid).values(revision=2, active=False))
            return real(stmt, *a, **k)

        c.execute = racing                                              # type: ignore[method-assign]
        with __import__("pytest").raises(RuleConflict) as e:
            set_exclusion_active(c, xid, False, "buyer-2", expected_revision=1)
        c.execute = real                                                # type: ignore[method-assign]
        assert e.value.current_revision == 2 and exclusion_revision(c, xid) == 2


def test_a_censoring_rule_save_needs_the_current_revision_once_one_exists(client, engine):
    seed(engine)
    rule = "/demand-rules/rules/min_zero_stock_days"
    assert client.put(rule, json={"value": 3}, headers=auth("buyer")).json()["revision"] == 1          # first save: nothing to be stale against
    assert client.put(rule, json={"value": 4}, headers=auth("buyer")).status_code == 428
    assert client.put(rule, json={"value": 4}, headers={**auth("buyer"), **IF1}).json()["revision"] == 2
    stale = client.put(rule, json={"value": 5}, headers={**auth("buyer"), **IF1})
    assert stale.status_code == 412 and stale.json()["current_version"] == 2


def test_the_segments_of_a_product_come_by_sku_critical_first(client, engine):
    seed(engine)
    with engine.begin() as c:
        c.execute(insert(product_segments).values(variant_id=1, abc="A", xyz="X", pattern="smooth", forecast_eligible=True, reason="", metrics={},
                                                  computed_at=datetime(2026, 11, 9, tzinfo=UTC), run_id="r1"))
    assert client.get("/products/syn-1/segments", headers=auth()).json() == {"sku": "SYN-1", "segments": ["A"]}
    client.put("/products/SYN-1/criticality", json={"critical": True}, headers=auth("buyer"))
    assert client.get("/products/SYN-1/segments", headers=auth()).json()["segments"] == ["critical", "A"]
    assert client.get("/products/NOPE/segments", headers=auth()).json()["detail"] == "sku_unknown"


def test_the_audit_read_is_admin_only_lists_rule_changes_and_shows_skus_not_ids(client, engine):
    seed(engine)
    client.post("/demand-rules/exclusions", json={**BODY, "detail": "campaña de otoño"}, headers=auth("buyer"))
    client.put("/demand-rules/rules/min_zero_stock_days", json={"value": 3}, headers=auth("buyer"))
    client.put("/products/SYN-1/criticality", json={"critical": True}, headers=auth("buyer"))
    assert client.get("/policy-audit", headers=auth("buyer")).status_code == 403
    items = client.get("/policy-audit", headers=auth("admin")).json()["items"]
    assert {i["action"] for i in items} == {"demand_exclusion.added", "censoring_rule.saved", "criticality.changed"}
    text = str(items)
    assert "variant_id" not in text and "campaña" not in text and "SYN-1" in text


def test_an_older_audit_event_with_free_text_never_reaches_the_audit_view(client, engine):
    """T055: before feature 011 the exclusion reason was written to the audit as typed text; the view shows only whitelisted keys."""
    from audit import append

    with engine.begin() as c:
        append(c, "buyer-0", "demand_exclusion.added", "demand_exclusion", "1", after={"variant_id": 1, "from": "2026-10-03", "to": "2026-10-03", "reason": "campaña de otoño"})
    items = client.get("/policy-audit", headers=auth("admin")).json()["items"]
    assert len(items) == 1 and items[0]["after"] == {"from": "2026-10-03", "to": "2026-10-03"}
    assert "campaña" not in str(items) and "variant_id" not in str(items)


def test_the_series_export_carries_the_rule_versions(client, engine):
    seed(engine)
    assert client.get("/export/series", headers=auth()).json()["rule_versions"] == {"exclusions": 0, "censoring.min_zero_stock_days": 0}
    xid = client.post("/demand-rules/exclusions", json=BODY, headers=auth("buyer")).json()["id"]
    client.put(f"/demand-rules/exclusions/{xid}", json={"active": False}, headers={**auth("buyer"), **IF1})
    client.put("/demand-rules/rules/min_zero_stock_days", json={"value": 3}, headers=auth("buyer"))
    assert client.get("/export/series", headers=auth()).json()["rule_versions"] == {"exclusions": 2, "censoring.min_zero_stock_days": 1}
