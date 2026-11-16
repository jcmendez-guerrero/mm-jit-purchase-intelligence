"""T068 (inventory): hostile SKUs, days and bodies on the quality endpoints are refused cleanly; no free text or tax id is stored (FR-021, rules 6 and 7)."""

import pytest
from conftest import auth
from db.tables import anomaly_flags, audit_events, data_quality_snapshot
from sqlalchemy import func, select
from test_quality_api import seed_case

HOSTILE_SKUS = ["x' OR '1'='1", "a; DROP TABLE anomaly_flags;--", "../../etc/passwd", "%00", "A" * 5000, "<script>alert(1)</script>"]


@pytest.mark.parametrize("sku", HOSTILE_SKUS)
def test_hostile_skus_are_not_found_and_never_crash_or_touch_data(client, engine, sku):
    seed_case(engine, "smooth")
    for path in (f"/quality/products/{sku}", f"/quality/products/{sku}/anomalies"):
        assert client.get(path, headers=auth()).status_code in (404, 422)
    assert client.put(f"/quality/products/{sku}/anomalies/2026-01-02", json={"decision": "accepted"}, headers=auth("buyer")).status_code in (404, 422)
    with engine.connect() as c:                                                    # the tables are still there and untouched
        assert c.execute(select(func.count()).select_from(anomaly_flags)).scalar() == 0


@pytest.mark.parametrize("day", ["not-a-day", "2026-13-40", "9999999999", "' OR 1=1"])
def test_a_malformed_day_is_a_validation_error(client, engine, day):
    sku, _ = seed_case(engine, "smooth")
    assert client.put(f"/quality/products/{sku}/anomalies/{day}", json={"decision": "accepted"}, headers=auth("buyer")).status_code == 422


@pytest.mark.parametrize("body", [{}, {"decision": 5}, {"decision": "x" * 10000}, {"decision": "excluded", "reason_code": "r" * 5000}, ["not", "an", "object"]])
def test_malformed_or_oversized_decision_bodies_are_refused_without_a_server_error(client, engine, body):
    sku, _ = seed_case(engine, "smooth")
    assert client.put(f"/quality/products/{sku}/anomalies/2026-01-02", json=body, headers=auth("buyer")).status_code in (404, 422)


def test_unparseable_json_is_a_validation_error(client, engine):
    sku, _ = seed_case(engine, "smooth")
    r = client.put(f"/quality/products/{sku}/anomalies/2026-01-02", content=b"{not json", headers={**auth("buyer"), "Content-Type": "application/json"})
    assert r.status_code == 422


def test_free_text_and_tax_id_fields_are_ignored_and_never_stored(client, engine):
    sku, _ = seed_case(engine, "smooth")
    body = {"decision": "accepted", "note": "texto libre secreto", "supplier_cif": "B12345678", "tax_id": "B12345678"}
    client.put(f"/quality/products/{sku}/anomalies/2026-01-02", json=body, headers=auth("buyer"))
    client.post("/quality/recompute", headers=auth("buyer"))
    with engine.connect() as c:
        stored = " ".join(str(v) for t in (anomaly_flags, data_quality_snapshot, audit_events) for r in c.execute(select(t)).all() for v in r)
    assert "texto libre secreto" not in stored and "B12345678" not in stored
