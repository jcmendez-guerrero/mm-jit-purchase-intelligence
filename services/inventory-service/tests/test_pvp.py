"""T066: the selling price is the variant price synchronised from the ERP, treated as net of VAT."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from conftest import auth
from db.tables import variants
from sqlalchemy import insert


def variant(c, vid, price, confirmed=None):
    c.execute(insert(variants).values(external_id=vid, sku=f"SYN-{vid}", name="V", pack_size=1, uom="unit", price=price,
                                      price_confirmed_at=confirmed if confirmed is not None else datetime.now(UTC)))


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


def test_a_price_confirmed_more_than_seven_days_ago_is_stale_and_shows_its_age(client, engine):
    now = datetime.now(UTC)
    with engine.begin() as c:
        variant(c, 1, Decimal("10"), now - timedelta(days=6, hours=23))
        variant(c, 2, Decimal("11"), now - timedelta(days=7, hours=1))
        variant(c, 3, Decimal("12"), now - timedelta(days=30))
    by = {p["variant_id"]: p for p in client.get("/pvp?variant_ids=1,2,3", headers=auth()).json()["prices"]}
    assert by[1]["stale"] is False and by[2]["stale"] is True and by[3]["stale"] is True
    assert by[1]["as_of"].startswith((now - timedelta(days=6, hours=23)).date().isoformat())
    assert by[3]["age_days"] == 30 and by[1]["age_days"] == 6


def test_a_price_with_no_confirmation_time_is_stale(client, engine):
    with engine.begin() as c:
        c.execute(insert(variants).values(external_id=9, sku="S", name="V", pack_size=1, uom="unit", price=Decimal("5")))
    (p,) = client.get("/pvp?variant_ids=9", headers=auth()).json()["prices"]
    assert p["stale"] is True and p["as_of"] is None and p["age_days"] is None
