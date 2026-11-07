"""T164: every sync that carries a price re-confirms it; a sync without a price does not."""

from datetime import UTC, date, datetime

from db.tables import variants
from projections.apply import apply_payload
from sqlalchemy import select


def rec(price_cents):
    r = {"id": 1, "sku": "S", "name": "V", "pack_size": 1, "uom": "unit", "total_on_hand": 1}
    if price_cents is not None:
        r["price_cents"] = price_cents
    return r


def confirmed(conn):
    return conn.execute(select(variants.c.price_confirmed_at)).scalar()


def test_a_sync_with_a_price_stamps_the_confirmation_time_and_one_without_clears_price_and_time(engine):
    before = datetime.now(UTC)
    with engine.begin() as c:
        apply_payload(c, {"kind": "variants", "records": [rec(1250)]}, date(2026, 11, 9))
    with engine.connect() as c:
        first = confirmed(c)
    assert first is not None and first.replace(tzinfo=UTC) >= before.replace(microsecond=0)
    with engine.begin() as c:
        apply_payload(c, {"kind": "variants", "records": [rec(None)]}, date(2026, 11, 10))
    with engine.connect() as c:
        assert confirmed(c) is None and c.execute(select(variants.c.price)).scalar() is None      # no price in the sync: nothing is confirmed
