"""Feature 014 (T051, US6, 006 FR-018): figures from locally loaded exports are labelled and never added to figures collected from the ERP.

Locally loaded products carry surrogate ids from 9,000,000 up. With both kinds in one database the dashboard shows the ERP figures and counts what it left out; with only local data it shows
those, labelled as a local load. Synthetic data only: the ERP reference dataset (stock value 100.00) plus one local product with 7 units at 3.00 (21.00).
"""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest
from conftest import auth
from dashboard.drilldown import drilldown
from dashboard.filters import FilterSet
from dashboard.indicators import build_indicators
from dashboard.kpis import LOCAL_ID_BASE, Filters, compute_summary, data_origin
from db.tables import ALL_WAREHOUSES, lot_cost_projection, products, stock_lots, stock_snapshots, variants
from reference_dataset import NOW, TODAY, freeze_clock, seed_reference
from sqlalchemy import insert

LOCAL = LOCAL_ID_BASE + 1


def seed_local(engine):
    with engine.begin() as c:
        c.execute(insert(products).values(external_id=LOCAL, name="Producto de carga local", status="active", missed_syncs=0, clinical_critical=False))
        c.execute(insert(variants).values(external_id=LOCAL, product_id=LOCAL, sku="LOC-001", name="Producto de carga local", pack_size=1, uom="u", reorder_point=1, price=9))
        c.execute(insert(stock_lots).values(variant_id=LOCAL, warehouse_id=1, batch_number="LB1", expiry_date=TODAY + timedelta(days=20), quantity=7, seen_at=NOW))
        c.execute(insert(lot_cost_projection).values(variant_id=LOCAL, supplier_id="sup-local", lot="LB1", unit_cost=Decimal("3.00"), source="local", updated_at=NOW))
        c.execute(insert(stock_snapshots).values(variant_id=LOCAL, warehouse_id=ALL_WAREHOUSES, snapshot_date=TODAY, on_hand=7, available=7, reserved=0))


def figures(engine):
    with engine.connect() as c:
        return {i["key"]: i for i in build_indicators(c, TODAY, FilterSet.parse(TODAY), None, ["buyer"], None, NOW)["indicators"]}


@pytest.fixture
def mixed(engine, monkeypatch):
    freeze_clock(monkeypatch)
    seed_reference(engine)
    seed_local(engine)
    return engine


def test_with_both_kinds_the_figures_are_the_erp_ones_and_the_local_products_are_counted_not_added(mixed):
    with mixed.connect() as c:
        assert data_origin(c) == ("erp_sync", 1)
        assert compute_summary(c, TODAY).inventory_value == Decimal("100")                  # not 121: the local lot is never added
        assert compute_summary(c, TODAY).expiring_value == Decimal("60")
    stock = figures(mixed)["stock_value"]
    assert Decimal(stock["value"]) == Decimal("100") and stock["freshness"]["origin"] == "erp_sync"


def test_the_products_behind_a_figure_never_include_a_local_product_next_to_erp_ones(mixed):
    with mixed.connect() as c:
        out = drilldown(c, "inventory_value", TODAY, Filters(), limit=200)
    assert "LOC-001" not in [r["sku"] for r in out["rows"]] and Decimal(out["sum"]) == Decimal("100")


def test_with_only_local_data_the_figures_are_those_and_every_card_says_it_is_a_local_load(engine, monkeypatch):
    freeze_clock(monkeypatch)
    seed_local(engine)
    with engine.connect() as c:
        assert data_origin(c) == ("local_load", 0)
        assert compute_summary(c, TODAY).inventory_value == Decimal("21")
    rows = figures(engine)
    assert Decimal(rows["stock_value"]["value"]) == Decimal("21") and rows["stock_value"]["freshness"]["origin"] == "local_load"
    assert rows["demand"]["freshness"]["origin"] == "local_load"


def test_an_empty_database_is_neither_kind_and_stays_erp_with_nothing_excluded(engine):
    with engine.connect() as c:
        assert data_origin(c) == ("erp_sync", 0)


def test_the_freshness_route_reports_the_origin_and_how_many_local_products_were_left_out(client, mixed):
    body = client.get("/dashboard/freshness", headers=auth("viewer")).json()
    assert body["local_load_excluded"] == 1 and {s["origin"] for s in body["sources"] if s["source"] != "aggregates"} == {"erp_sync"}


def test_the_freshness_payload_matches_its_contract(client, mixed):
    schema = json.loads((Path(__file__).resolve().parents[3] / "packages" / "contracts" / "dto" / "dashboard_freshness.v1.schema.json").read_text(encoding="utf-8"))
    body = client.get("/dashboard/freshness", headers=auth("viewer")).json()
    jsonschema.validate(body, schema, cls=jsonschema.Draft202012Validator)
    assert body["review_list_link"] == "/calidad" and {s["source"] for s in body["sources"]} >= {"inventory_snapshot", "movements"}
