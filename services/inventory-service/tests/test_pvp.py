"""T066 (assumption): the selling price comes from the newest priced movement and is labelled as such."""

from datetime import UTC, datetime

from conftest import auth
from db.tables import stock_movements
from sqlalchemy import insert


def mv(c, ext, variant, price, hour, quarantined=False):
    c.execute(insert(stock_movements).values(external_id=ext, created_at_utc=datetime(2026, 11, 3, hour, tzinfo=UTC), created_at_raw="x", variant_id=variant, warehouse_id=1,
                                             quantity=1, reason="sale_shipment", unit_cost=price, has_note=False, quarantined=quarantined))


def test_latest_priced_unquarantined_movement_wins_and_missing_variants_are_omitted(client, engine):
    with engine.begin() as c:
        mv(c, 1, 1, "10.00", 8)
        mv(c, 2, 1, "12.50", 9)
        mv(c, 3, 1, "99.00", 10, quarantined=True)
        mv(c, 4, 2, None, 9)
    body = client.get("/pvp?variant_ids=1,2,3", headers=auth()).json()["prices"]
    from decimal import Decimal

    assert [(p["variant_id"], Decimal(p["pvp"]), p["source"]) for p in body] == [(1, Decimal("12.5"), "stock_movement_price")]
    assert {p["variant_id"] for p in body} == {1}


def test_requires_authentication_and_valid_ids(client):
    assert client.get("/pvp?variant_ids=1").status_code == 401
    assert client.get("/pvp?variant_ids=x", headers=auth()).status_code == 422
