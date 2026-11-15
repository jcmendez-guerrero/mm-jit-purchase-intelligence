"""T019: an excluded anomaly day becomes censored in the series export and never changes the ERP-derived demand rows (research R3)."""

from conftest import auth
from db.tables import demand_observations
from sqlalchemy import select
from test_quality_api import seed_case

DAY_INDEX = 70                         # 2026-03-12, the fixture's outlier day


def export_for(client, vid):
    return next(s for s in client.get("/export/series", headers=auth()).json()["series"] if s["variant_id"] == vid)


def demand_rows(engine):
    with engine.begin() as c:
        return [tuple(r) for r in c.execute(select(demand_observations).order_by(demand_observations.c.variant_id, demand_observations.c.day)).all()]


def test_an_excluded_day_reads_as_censored_while_the_demand_rows_stay_untouched(client, engine):
    sku, vid = seed_case(engine, "outlier")
    before_rows, before = demand_rows(engine), export_for(client, vid)
    assert before["censored"][DAY_INDEX] is False

    url = f"/quality/products/{sku}/anomalies/2026-03-12"
    assert client.put(url, json={"decision": "excluded", "reason_code": "data_error"}, headers=auth("buyer")).json()["changed"] is True
    after = export_for(client, vid)
    assert after["censored"][DAY_INDEX] is True and after["demand"][DAY_INDEX] == before["demand"][DAY_INDEX] == 90     # the original value is still reported
    assert sum(after["censored"]) == sum(before["censored"]) + 1
    assert demand_rows(engine) == before_rows                                                                          # ERP-derived rows untouched
    assert after != before                                                                                             # a new series version: a new forecast input


def test_accepting_or_reverting_restores_the_day_exactly(client, engine):
    sku, vid = seed_case(engine, "outlier")
    before = export_for(client, vid)
    url = f"/quality/products/{sku}/anomalies/2026-03-12"
    client.put(url, json={"decision": "excluded"}, headers=auth("buyer"))
    client.put(url, json={"decision": "accepted"}, headers=auth("buyer"))
    assert export_for(client, vid) == before


def test_other_products_are_not_affected(client, engine):
    sku, _ = seed_case(engine, "outlier")
    _, smooth_vid = seed_case(engine, "smooth")
    other_before = export_for(client, smooth_vid)
    client.put(f"/quality/products/{sku}/anomalies/2026-03-12", json={"decision": "excluded"}, headers=auth("buyer"))
    assert export_for(client, smooth_vid) == other_before
