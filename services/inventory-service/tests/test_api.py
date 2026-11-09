"""Inventory API (T057 and the US3 endpoints)."""

from datetime import date
from decimal import Decimal

from conftest import auth
from db.tables import variants
from demand.rebuild import rebuild
from sqlalchemy import insert
from test_review_and_metrics import T, add, snapshot


def test_api_requires_authentication_and_the_buyer_role_for_decisions(client, engine):
    assert client.get("/review").status_code == 401
    assert client.post("/review/decisions", json={"ids": [1], "decision": "confirm"}, headers=auth("viewer")).status_code == 403


def test_api_variant_detail_and_review_flow(client, engine):
    with engine.begin() as c:
        c.execute(insert(variants).values(external_id=1, sku="SYN-1", name="Variante", pack_size=1, uom="unit"))
    add(engine, 1, "initial_stock", 10, T(1))
    add(engine, 2, "sale_shipment", -4, T(2))
    add(engine, 3, "sale_shipment", -1, T(3), quarantined=True, codes="unreferenced_sale")
    snapshot(engine, 1, date(2026, 10, 5), 5)
    with engine.begin() as c:
        rebuild(c)
    assert client.get("/variants/999", headers=auth()).status_code == 404
    body = client.get("/variants/1", headers=auth()).json()
    assert body["stock"]["on_hand"] == 5 and [d["qty"] for d in body["demand"]] == [4] and body["history_reconciled"] is True
    assert client.get("/review", headers=auth()).json()["count"] == 1
    assert client.post("/review/decisions", json={"ids": [99], "decision": "confirm"}, headers=auth("buyer")).status_code == 409
    assert client.post("/review/decisions", json={"ids": [3], "decision": "confirm"}, headers=auth("buyer")).json() == {"decided": 1}
    assert [d["qty"] for d in client.get("/variants/1", headers=auth()).json()["demand"]] == [4, 1]
    assert client.get("/review", headers=auth()).json()["count"] == 0


def test_criticality_and_service_level_endpoints(client, engine):
    from db.tables import products

    with engine.begin() as c:
        c.execute(insert(products).values(external_id=5, name="P", status="active", missed_syncs=0))
    assert client.put("/products/5/criticality", json={"critical": True}, headers=auth("viewer")).status_code == 403
    assert client.put("/products/5/criticality", json={"critical": True}, headers=auth("buyer")).json()["changed"] is True
    assert client.put("/products/99/criticality", json={"critical": True}, headers=auth("buyer")).status_code == 404
    # service levels are edited in procurement policies (ADR-018, T006); inventory keeps its history readable and offers no edit route
    assert client.put("/service-levels", json={"scope": "abc", "key": "A", "target": "0.98"}, headers=auth("buyer")).status_code == 405
    from classification.service_levels import set_target

    with engine.begin() as c:
        set_target(c, "abc", "A", Decimal("0.98"), "legacy")
    assert [h["target"] for h in client.get("/service-levels", headers=auth()).json()["history"]] == ["0.9800"]


def test_export_series_carries_segment_and_service_level(client, engine):
    from classification.run import compute_segments
    from test_classification import SMOOTH, seed_variant

    seed_variant(engine, 1, 1, SMOOTH, price="20")
    with engine.begin() as c:
        compute_segments(c)
    client.put("/products/1/criticality", json={"critical": True}, headers=auth("buyer"))
    body = client.get("/export/series", headers=auth()).json()
    s = body["series"][0]
    assert body["count"] == 1 and len(s["demand"]) == len(s["censored"]) == len(SMOOTH) * 7
    assert s["segment"]["pattern"] == "smooth" and s["service_level"] == "0.99" and s["clinical_critical"] is True
    assert isinstance(s["sku"], str) and s["sku"]               # MMI-7: the seed import resolves SKU from the series export
    detail = client.get("/variants/1", headers=auth()).json()
    assert detail["segment"]["abc"] == "A" and detail["segment"]["forecast_eligible"] is True
