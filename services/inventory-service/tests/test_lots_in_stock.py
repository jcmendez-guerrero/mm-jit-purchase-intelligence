"""T058: lots in stock for the cost median."""

from datetime import UTC, datetime

from conftest import auth
from db.tables import stock_lots
from sqlalchemy import insert

NOW = datetime(2026, 11, 4, 8, 0, tzinfo=UTC)


def lot(c, variant, wh, batch, qty):
    c.execute(insert(stock_lots).values(variant_id=variant, warehouse_id=wh, batch_number=batch, quantity=qty, seen_at=NOW))


def test_sums_remaining_quantity_per_batch_across_warehouses_and_skips_empty_lots(client, engine):
    with engine.begin() as c:
        lot(c, 1, 1, "L1", 4)
        lot(c, 1, 2, "L1", 3)
        lot(c, 1, 1, "L2", 0)
        lot(c, 1, 1, None, 2)
        lot(c, 2, 1, "L9", 5)
    rows = client.get("/lots/in-stock?variant_ids=1", headers=auth()).json()["lots"]
    assert {(r["lot"], r["quantity"]) for r in rows} == {("L1", 7), (None, 2)}
    assert {r["variant_id"] for r in client.get("/lots/in-stock?variant_ids=1,2", headers=auth()).json()["lots"]} == {1, 2}


def test_requires_authentication_and_valid_ids(client):
    assert client.get("/lots/in-stock?variant_ids=1").status_code == 401
    for bad in ("", "a", "0", "1,-2", ",".join(str(i) for i in range(1, 202))):
        assert client.get(f"/lots/in-stock?variant_ids={bad}", headers=auth()).status_code == 422
