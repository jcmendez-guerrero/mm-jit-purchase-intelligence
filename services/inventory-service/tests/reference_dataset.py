"""Loads the synthetic dashboard reference dataset (packages/testing/fixtures/dashboard_reference) into an engine. Expected totals: TOTALS.md next to the data."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from db.tables import (
    ALL_WAREHOUSES,
    demand_observations,
    lot_cost_projection,
    product_segments,
    products,
    stock_lots,
    stock_snapshots,
    variants,
    warehouses,
)
from sqlalchemy import insert

DATA = Path(__file__).resolve().parents[3] / "packages" / "testing" / "fixtures" / "dashboard_reference" / "dataset.json"
TODAY = date(2026, 11, 9)
NOW = datetime(2026, 11, 9, 8, tzinfo=UTC)


def freeze_clock(monkeypatch):
    """The reference data is dated 2026-11-09: freshness is measured against that moment, not the day the suite runs."""
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is None else NOW.astimezone(tz)

    monkeypatch.setattr("dashboard.freshness.datetime", Frozen)


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def seed_reference(engine) -> dict:
    ds = load()
    assert date.fromisoformat(ds["today"]) == TODAY
    with engine.begin() as c:
        c.execute(insert(products).values([{"external_id": p["external_id"], "name": p["name"], "status": "active", "missed_syncs": 0, "clinical_critical": p["clinical_critical"]} for p in ds["products"]]))
        c.execute(insert(variants).values([{"external_id": v["external_id"], "product_id": v["product_id"], "sku": v["sku"], "name": v["name"], "pack_size": 1, "uom": "u", "reorder_point": 2, "price": 99} for v in ds["variants"]]))
        c.execute(insert(warehouses).values([{"external_id": w["external_id"], "name": w["name"], "is_unassigned": False} for w in ds["warehouses"]]))
        c.execute(insert(stock_lots).values([{"variant_id": lot["variant_id"], "warehouse_id": lot["warehouse_id"], "batch_number": lot["batch"], "expiry_date": TODAY + timedelta(days=lot["expiry_offset_days"]),
                                              "quantity": lot["quantity"], "seen_at": NOW} for lot in ds["lots"]]))
        c.execute(insert(lot_cost_projection).values([{"variant_id": k["variant_id"], "supplier_id": k["supplier_id"], "lot": k["lot"], "unit_cost": Decimal(k["unit_cost"]), "source": k["source"], "updated_at": NOW} for k in ds["lot_costs"]]))
        per_variant: dict[int, int] = {}
        per_pair: dict[tuple[int, int], int] = {}
        for lot in ds["lots"]:
            per_variant[lot["variant_id"]] = per_variant.get(lot["variant_id"], 0) + lot["quantity"]
            per_pair[(lot["variant_id"], lot["warehouse_id"])] = per_pair.get((lot["variant_id"], lot["warehouse_id"]), 0) + lot["quantity"]
        snaps = [(v, ALL_WAREHOUSES, q) for v, q in per_variant.items()] + [(v, w, q) for (v, w), q in per_pair.items()]
        c.execute(insert(stock_snapshots).values([{"variant_id": v, "warehouse_id": w, "snapshot_date": TODAY, "on_hand": q, "available": q, "reserved": 0} for v, w, q in snaps]))
        c.execute(insert(product_segments).values([{"variant_id": s["variant_id"], "abc": s["abc"], "xyz": s["xyz"], "pattern": s["pattern"], "forecast_eligible": s["eligible"],
                                                    "reason": "" if s["eligible"] else "too_sparse", "metrics": {"value": s["value"]}, "computed_at": NOW, "run_id": "r"} for s in ds["segments"]]))
        d = ds["demand"]
        rows = []
        for i in range(d["days"]):
            for p in d["per_day"]:
                rows.append({"variant_id": p["variant_id"], "warehouse_id": p["warehouse_id"], "day": TODAY - timedelta(days=i), "demand_qty": p["qty"],
                             "censored": i == 0 and p["variant_id"] in d["censored_today_for"], "lineage": "movements"})
        c.execute(insert(demand_observations).values(rows))
    return ds
