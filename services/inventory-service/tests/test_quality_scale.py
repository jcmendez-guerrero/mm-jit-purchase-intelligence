"""T092 (feature 018, SC-006, FR-022): recomputing quality for 5,000 products stays inside the 20 seconds a request may take.

Past that limit the recompute has to move to the background (T025); this test is the signal that tells us so. It runs on PostgreSQL in CI, where the
one-product-at-a-time version took 30 to 33 s; the batched rebuild (T094) takes under 4 s.
"""

import time
from datetime import date, timedelta

from conftest import auth
from db.tables import ALL_WAREHOUSES, demand_observations, products, stock_history, variants
from sqlalchemy import insert

LIMIT_SECONDS = 20
PRODUCTS = 5000
DAYS = 90
START = date(2026, 1, 1)


def seed(engine):
    ids = range(1, PRODUCTS + 1)
    days = [START + timedelta(days=d) for d in range(DAYS)]
    with engine.begin() as c:
        c.execute(insert(products), [{"external_id": i, "name": f"P{i}", "status": "active", "missed_syncs": 0} for i in ids])
        c.execute(insert(variants), [{"external_id": i, "product_id": i, "sku": f"SYN-{i:05d}", "price": 5} for i in ids])
        c.execute(insert(stock_history), [{"variant_id": i, "warehouse_id": ALL_WAREHOUSES, "day": d, "on_hand_reconstructed": 50, "censored": (d.day + i) % 29 == 0, "reconciled_ok": True}
                                          for i in ids for d in days])
        c.execute(insert(demand_observations), [{"variant_id": i, "warehouse_id": 1, "day": d, "demand_qty": 1 + (i + d.day) % 4, "censored": False, "lineage": "x"}
                                                for i in ids for d in days if (d.day + i) % 3 == 0])


def test_recomputing_five_thousand_products_stays_inside_the_limit(client, engine):
    seed(engine)
    started = time.monotonic()
    r = client.post("/quality/recompute", headers=auth("buyer"))
    elapsed = time.monotonic() - started
    assert r.status_code == 200 and r.json()["products"] == PRODUCTS and elapsed < LIMIT_SECONDS, f"{elapsed:.0f}s for {PRODUCTS} products"
