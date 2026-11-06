"""T066: the selling price is the variant price synchronised from the ERP, treated as net of VAT."""

from decimal import Decimal

from conftest import auth
from db.tables import variants
from sqlalchemy import insert


def variant(c, vid, price):
    c.execute(insert(variants).values(external_id=vid, sku=f"SYN-{vid}", name="V", pack_size=1, uom="unit", price=price))


def test_returns_the_variant_price_as_is_and_omits_variants_without_one(client, engine):
    with engine.begin() as c:
        variant(c, 1, Decimal("12.50"))
        variant(c, 2, None)
        variant(c, 3, Decimal("0"))
    body = client.get("/pvp?variant_ids=1,2,3,4", headers=auth()).json()["prices"]
    assert [(p["variant_id"], Decimal(p["pvp"]), p["source"]) for p in body] == [(1, Decimal("12.5"), "variant_price")]


def test_requires_authentication_and_valid_ids(client):
    assert client.get("/pvp?variant_ids=1").status_code == 401
    assert client.get("/pvp?variant_ids=x", headers=auth()).status_code == 422
