"""T017: quality summary, anomaly decisions and recompute endpoints (feature 012; roles, idempotency, audit, error codes)."""

from datetime import date, timedelta

import quality_fixtures as qf
from audit import verify_chain
from conftest import auth
from db.tables import (
    ALL_WAREHOUSES,
    audit_events,
    data_quality_snapshot,
    demand_observations,
    products,
    stock_history,
    variants,
)
from sqlalchemy import delete, func, insert, select

FROM, TO = "2026-01-01", "2026-04-30"          # the 120 fixture days


def seed_case(engine, name):
    """Loads one quality fixture (feature 012, packages/testing) into the inventory tables; returns its SKU and variant id."""
    s = qf.build_series(name)
    vid, start = s["variant_id"], date.fromisoformat(s["start_day"])
    days = [start + timedelta(days=i) for i in range(len(s["demand"]))]
    with engine.begin() as c:
        c.execute(insert(products).values(external_id=vid, name=f"P{vid}", status="active", missed_syncs=0))
        c.execute(insert(variants).values(external_id=vid, product_id=vid, sku=s["sku"], price=10))
        c.execute(insert(stock_history), [{"variant_id": vid, "warehouse_id": ALL_WAREHOUSES, "day": d, "on_hand_reconstructed": 50, "censored": bool(cz), "reconciled_ok": True}
                                          for d, cz in zip(days, s["censored"], strict=True)])
        c.execute(insert(demand_observations), [{"variant_id": vid, "warehouse_id": 1, "day": d, "demand_qty": q, "censored": False, "lineage": "x"}
                                                for d, q in zip(days, s["demand"], strict=True) if q != 0])
    return s["sku"], vid


def test_the_summary_is_readable_by_a_viewer_and_reports_full_coverage(client, engine):
    sku, _ = seed_case(engine, "smooth")
    body = client.get(f"/quality/products/{sku}?from={FROM}&to={TO}", headers=auth("viewer")).json()
    assert body["sku"] == sku and body["days_in_period"] == 120 and body["days_with_data"] == 120 and body["coverage_ratio"] == "1.000000"
    assert body["gap_days"] == [] and body["origin"] == "erp" and body["anomaly_count"] == 0 and body["censored_days"] == 0


def test_gap_days_and_stockout_days_are_reported(client, engine):
    sku, vid = seed_case(engine, "stockout")
    with engine.begin() as c:
        c.execute(delete(stock_history).where(stock_history.c.variant_id == vid, stock_history.c.day.between(date(2026, 1, 11), date(2026, 1, 15))))
        c.execute(delete(demand_observations).where(demand_observations.c.variant_id == vid, demand_observations.c.day.between(date(2026, 1, 11), date(2026, 1, 15))))
    body = client.get(f"/quality/products/{sku}?from={FROM}&to={TO}", headers=auth()).json()
    assert body["days_with_data"] == 115 and body["gap_days"] == [{"from": "2026-01-11", "to": "2026-01-15"}]
    assert body["censored_days"] == len(qf.STOCKOUT_DAYS)


def test_unknown_sku_and_bad_period_use_error_codes(client, engine):
    sku, _ = seed_case(engine, "smooth")
    assert client.get("/quality/products/NOPE", headers=auth()).json()["detail"] == "quality_product_not_found"
    assert client.get(f"/quality/products/{sku}?from=2026-03-02&to=2026-03-01", headers=auth()).status_code == 422
    assert client.get(f"/quality/products/{sku}").status_code == 401


def test_an_ambiguous_sku_is_never_guessed(client, engine):
    sku, vid = seed_case(engine, "smooth")
    with engine.begin() as c:
        c.execute(insert(variants).values(external_id=vid + 1000, product_id=vid, sku=sku, price=10))
    r = client.get(f"/quality/products/{sku}", headers=auth())
    assert r.status_code == 422 and r.json()["detail"] == "import_ambiguous_sku"


def test_anomalies_are_listed_with_rule_and_original_value(client, engine):
    sku, _ = seed_case(engine, "outlier")
    flags = client.get(f"/quality/products/{sku}/anomalies", headers=auth("viewer")).json()["anomalies"]
    assert {(f["rule_id"], f["original_value"], f["decision"]) for f in flags} == {("mad_outlier", "90", "pending"), ("p95_cap", "90", "pending")}
    assert {f["day"] for f in flags} == {"2026-03-12"} and all(f["sku"] == sku for f in flags)


def test_decisions_need_a_buyer_or_admin_and_are_idempotent_and_audited(client, engine):
    sku, _ = seed_case(engine, "outlier")
    url = f"/quality/products/{sku}/anomalies/2026-03-12"
    assert client.put(url, json={"decision": "excluded"}, headers=auth("viewer")).status_code == 403
    first = client.put(url, json={"decision": "excluded", "reason_code": "data_error"}, headers={**auth("buyer"), "X-Fresh-Second-Factor": "true"}).json()
    again = client.put(url, json={"decision": "excluded", "reason_code": "data_error"}, headers={**auth("buyer"), "X-Fresh-Second-Factor": "true"}).json()
    assert first["changed"] is True and again["changed"] is False
    assert client.put(url, json={"decision": "accepted"}, headers={**auth("admin"), "X-Fresh-Second-Factor": "true"}).json()["changed"] is True
    with engine.begin() as c:
        assert c.execute(select(func.count()).select_from(audit_events)).scalar() == 2          # only real changes are audited
        assert verify_chain(c).ok
        row = c.execute(select(audit_events).order_by(audit_events.c.id).limit(1)).first()
    assert row.action == "quality.anomaly_decided" and row.after["reason_code"] == "data_error"


def test_bad_decisions_reasons_and_days_are_refused_with_codes(client, engine):
    sku, _ = seed_case(engine, "outlier")
    url = f"/quality/products/{sku}/anomalies/2026-03-12"
    assert client.put(url, json={"decision": "deleted"}, headers=auth("buyer")).json()["detail"] == "quality_decision_invalid"
    assert client.put(url, json={"decision": "excluded", "reason_code": "free text here"}, headers={**auth("buyer"), "X-Fresh-Second-Factor": "true"}).json()["detail"] == "quality_decision_invalid"
    assert client.put(f"/quality/products/{sku}/anomalies/2026-02-01", json={"decision": "excluded"}, headers={**auth("buyer"), "X-Fresh-Second-Factor": "true"}).json()["detail"] == "quality_anomaly_not_found"


def test_recompute_is_restricted_idempotent_and_does_not_duplicate_snapshots(client, engine):
    seed_case(engine, "smooth")
    seed_case(engine, "outlier")
    assert client.post("/quality/recompute", headers=auth("viewer")).status_code == 403
    one = client.post("/quality/recompute", headers=auth("buyer")).json()
    two = client.post("/quality/recompute", headers=auth("buyer")).json()
    assert one["job_id"] == two["job_id"] and one["status"] == "completed" and one["products"] == 2
    with engine.begin() as c:
        assert c.execute(select(func.count()).select_from(data_quality_snapshot)).scalar() == 2
