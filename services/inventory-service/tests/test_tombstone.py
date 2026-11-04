"""T141: a product is discontinued only after N consecutive missed syncs (default 3); reappearing reactivates;
a single failed (unreconciled) run never tombstones."""

from db.tables import products
from projections.consumer import consume_once
from sqlalchemy import select

P = lambda i: {"id": i, "name": f"Producto {i}", "status": "active"}  # noqa: E731


def state(engine, pid):
    with engine.connect() as c:
        r = c.execute(select(products.c.status, products.c.missed_syncs).where(products.c.external_id == pid)).one()
    return r.status, r.missed_syncs


def sync(engine, bus, blobs, publish, records, reconciled=True, n=3):
    publish("products", records, reconciled=reconciled)
    return consume_once(engine, bus, blobs, tombstone_after=n)


def test_discontinued_only_after_three_consecutive_misses(engine, bus, blobs, publish):
    sync(engine, bus, blobs, publish, [P(1), P(2)])
    for expected in [("active", 1), ("active", 2), ("discontinued", 3)]:
        sync(engine, bus, blobs, publish, [P(1)])
        assert state(engine, 2) == expected
    assert state(engine, 1) == ("active", 0)


def test_reappearance_reactivates_and_resets_the_counter(engine, bus, blobs, publish):
    sync(engine, bus, blobs, publish, [P(1), P(2)])
    for _ in range(3):
        sync(engine, bus, blobs, publish, [P(1)])
    assert state(engine, 2)[0] == "discontinued"
    sync(engine, bus, blobs, publish, [P(1), P(2)])
    assert state(engine, 2) == ("active", 0)


def test_a_reappearance_between_misses_resets_the_count(engine, bus, blobs, publish):
    sync(engine, bus, blobs, publish, [P(1), P(2)])
    sync(engine, bus, blobs, publish, [P(1)])
    sync(engine, bus, blobs, publish, [P(1)])
    sync(engine, bus, blobs, publish, [P(1), P(2)])
    sync(engine, bus, blobs, publish, [P(1)])
    assert state(engine, 2) == ("active", 1)


def test_unreconciled_run_never_tombstones(engine, bus, blobs, publish):
    sync(engine, bus, blobs, publish, [P(1), P(2)])
    for _ in range(5):
        sync(engine, bus, blobs, publish, [P(1)], reconciled=False)
    assert state(engine, 2) == ("active", 0)


def test_the_threshold_is_configurable(engine, bus, blobs, publish):
    sync(engine, bus, blobs, publish, [P(1), P(2)], n=1)
    sync(engine, bus, blobs, publish, [P(1)], n=1)
    assert state(engine, 2)[0] == "discontinued"


def test_buyer_vat_is_not_overwritten_by_a_sync_without_vat(engine, bus, blobs, publish):
    from sqlalchemy import update

    sync(engine, bus, blobs, publish, [P(1)])
    with engine.begin() as c:
        c.execute(update(products).values(vat_rate=10, clinical_critical=True))
    sync(engine, bus, blobs, publish, [P(1)])
    with engine.connect() as c:
        r = c.execute(select(products.c.vat_rate, products.c.clinical_critical)).one()
    assert float(r.vat_rate) == 10 and r.clinical_critical is True
