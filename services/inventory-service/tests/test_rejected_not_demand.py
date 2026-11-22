"""T018: rejected and quarantined movements never reach demand and show up in the quality summary with reason codes (SC-004)."""

from datetime import date

from conftest import auth
from db.tables import demand_observations, variants
from demand.rebuild import rebuild
from sqlalchemy import insert, select
from test_review_and_metrics import T, add, snapshot


def seed(engine):
    with engine.begin() as c:
        c.execute(insert(variants).values(external_id=1, sku="SYN-1", name="Variante", pack_size=1, uom="unit"))
    add(engine, 1, "initial_stock", 20, T(1))
    add(engine, 2, "sale_shipment", -4, T(2))
    add(engine, 3, "sale_shipment", -3, T(3), quarantined=True, codes="malformed_date,ambiguous_sku")
    add(engine, 4, "sale_shipment", -2, T(4), quarantined=True, codes="negative_quantity")
    add(engine, 5, "transfer_out", -1, T(5))
    snapshot(engine, 1, date(2026, 10, 6), 10)
    with engine.begin() as c:
        rebuild(c)


def demand_total(engine):
    with engine.begin() as c:
        return sum(r.demand_qty for r in c.execute(select(demand_observations)).all())


def test_quarantined_movements_are_not_demand_and_are_counted_with_their_reasons(client, engine):
    seed(engine)
    assert demand_total(engine) == 4                                    # only the clean sale; the two quarantined sales are excluded
    body = client.get("/quality/products/SYN-1", headers=auth()).json()
    assert body["quarantined_count"] == 2 and body["rejected_count"] == 0 and body["ambiguous_count"] == 1
    assert {(r["key"], r["count"]) for r in body["reason_counts"]} == {("malformed_date", 1), ("ambiguous_sku", 1), ("negative_quantity", 1)}


def test_non_sale_movements_are_reported_as_excluded_by_type(client, engine):
    seed(engine)
    body = client.get("/quality/products/SYN-1?from=2026-10-01&to=2026-10-31", headers=auth()).json()
    assert {(r["key"], r["count"]) for r in body["excluded_by_type"]} >= {("transfer_out", 1)}


def test_ignoring_a_quarantined_movement_moves_it_to_rejected_and_demand_stays_the_same(client, engine):
    seed(engine)
    assert client.post("/review/decisions", json={"ids": [4], "decision": "ignore"}, headers=auth("buyer")).json() == {"decided": 1}
    body = client.get("/quality/products/SYN-1", headers=auth()).json()
    assert body["rejected_count"] == 1 and body["quarantined_count"] == 1
    assert demand_total(engine) == 4


def test_confirming_releases_it_into_demand_and_out_of_the_quality_counts(client, engine):
    seed(engine)
    client.post("/review/decisions", json={"ids": [3], "decision": "confirm"}, headers=auth("buyer"))
    assert demand_total(engine) == 7
