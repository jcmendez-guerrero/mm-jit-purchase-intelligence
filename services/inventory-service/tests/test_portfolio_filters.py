"""T060: the portfolio's filters (category, family, supplier) narrow its counts and its lists the same way, and 5,000 products load fast (SC-006)."""

import time
from datetime import UTC, datetime
from decimal import Decimal

from conftest import auth
from dashboard.kpis import Filters
from db.tables import lot_cost_projection, product_segments, products, stock_lots, variants
from quality.portfolio import portfolio, rebuild_portfolio
from sqlalchemy import insert, update
from test_portfolio_reconcile import recompute, seed_all

NOW = datetime(2026, 11, 15, tzinfo=UTC)


def test_the_category_filter_keeps_only_that_class_and_every_distribution_still_adds_up(client, engine):
    seed_all(engine)
    recompute(client, None)
    everything = client.get("/quality/portfolio", headers=auth()).json()
    with engine.connect() as c:
        wanted = {r.variant_id for r in c.execute(product_segments.select().where(product_segments.c.abc == "A")).all()}
    body = client.get("/quality/portfolio?category=A", headers=auth()).json()
    assert body["active_products"] == len(wanted) and body["active_products"] < everything["active_products"]
    assert all(sum(b["count"] for b in body[k]) == len(wanted) for k in ("by_class", "by_eligibility", "by_confidence"))
    assert body["filters"] == {"category": "A", "supplier": None, "origin": "erp"}
    listed = client.get("/quality/portfolio/products?bucket=eligibility&key=pending&category=A", headers=auth()).json()
    assert listed["total"] == len(wanted)


def test_the_family_filter_keeps_only_that_family(client, engine):
    seed_all(engine)
    recompute(client, None)
    with engine.begin() as c:
        c.execute(update(products).where(products.c.external_id.in_([910101, 910102])).values(family="Antiparasitarios"))
    body = client.get("/quality/portfolio?family=Antiparasitarios", headers=auth()).json()
    assert body["active_products"] == 2
    assert client.get("/quality/portfolio/products?bucket=eligibility&key=pending&family=Antiparasitarios", headers=auth()).json()["skus"] == ["EJ-9101", "EJ-9102"]


def test_the_supplier_filter_keeps_only_products_with_stock_costed_from_that_supplier(client, engine):
    seed_all(engine)
    recompute(client, None)
    with engine.begin() as c:
        for vid in (910103, 910104):
            c.execute(insert(stock_lots).values(variant_id=vid, warehouse_id=1, batch_number="L1", quantity=5, seen_at=NOW))
            c.execute(insert(lot_cost_projection).values(variant_id=vid, supplier_id="s1", lot="L1", unit_cost=Decimal("2.5"), source="erp", updated_at=NOW))
    body = client.get("/quality/portfolio?supplier_id=s1", headers=auth()).json()
    assert body["active_products"] == 2 and body["filters"]["supplier"] == "s1"
    assert client.get("/quality/portfolio?supplier_id=other", headers=auth()).json()["active_products"] == 0


def test_filters_can_be_combined(client, engine):
    seed_all(engine)
    recompute(client, None)
    assert client.get("/quality/portfolio?category=A&supplier_id=nobody", headers=auth()).json()["active_products"] == 0


def test_five_thousand_products_load_in_under_three_seconds(engine):
    with engine.begin() as c:
        c.execute(insert(products), [{"external_id": i, "name": f"P{i}", "status": "active", "missed_syncs": 0} for i in range(1, 5001)])
        c.execute(insert(variants), [{"external_id": i, "product_id": i, "sku": f"EJ-{i}", "price": 10, "is_service": False} for i in range(1, 5001)])
        c.execute(insert(product_segments), [{"variant_id": i, "abc": "ABC"[i % 3], "xyz": "XYZ"[i % 3], "pattern": "smooth", "forecast_eligible": True, "reason": "", "metrics": {},
                                              "computed_at": NOW, "run_id": "r"} for i in range(1, 5001)])
        rebuild_portfolio(c, {f"EJ-{i}": ("eligible", "alta") for i in range(1, 5001, 2)}, "run-1")
    started = time.monotonic()
    with engine.connect() as c:
        body = portfolio(c, Filters())
    elapsed = time.monotonic() - started
    assert body["active_products"] == 5000 and sum(b["count"] for b in body["by_eligibility"]) == 5000 and elapsed < 3, f"{elapsed:.1f}s"
