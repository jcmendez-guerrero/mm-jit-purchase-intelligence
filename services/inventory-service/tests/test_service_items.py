"""T028 (FR-036): items of type service are stored and shown, but never enter stock, demand, segments, forecasting inputs or risks."""

from datetime import date
from decimal import Decimal

from classification.run import compute_segments, load_series
from conftest import auth
from dashboard.kpis import Filters, variant_scope
from db.tables import ALL_WAREHOUSES, demand_observations, product_segments, products, stock_history, variants
from projections.apply import apply_payload
from sqlalchemy import insert, select

END = date(2026, 10, 31)


def records():
    base = {"product_name": "P", "pack_size": 1, "uom": "unidad", "total_on_hand": 4, "category": "Familia sintética"}
    return [
        {**base, "id": 9000001, "product_id": 9000001, "sku": "SYN-000001", "name": "Producto físico", "price_cents": 1500},
        {**base, "id": 9000002, "product_id": 9000002, "sku": "SYN-000002", "name": "Servicio sintético", "price_cents": 3000, "is_service": True, "total_on_hand": 0},
    ]


def apply(engine):
    with engine.begin() as c:
        apply_payload(c, {"kind": "variants", "records": records()}, END)


def test_the_flag_is_stored_and_defaults_to_false(engine):
    apply(engine)
    with engine.connect() as c:
        flags = {r.sku: r.is_service for r in c.execute(select(variants.c.sku, variants.c.is_service)).all()}
    assert flags == {"SYN-000001": False, "SYN-000002": True}


def test_services_are_not_part_of_any_dashboard_scope(engine):
    apply(engine)
    with engine.connect() as c:
        assert variant_scope(c, Filters()) == {9000001}


def test_services_get_no_series_and_no_segment(engine):
    apply(engine)
    days = [date.fromordinal(END.toordinal() - i) for i in range(40)]
    with engine.begin() as c:
        for vid in (9000001, 9000002):
            c.execute(insert(stock_history), [{"variant_id": vid, "warehouse_id": ALL_WAREHOUSES, "day": d, "on_hand_reconstructed": 5,
                                               "censored": False, "reconciled_ok": True} for d in days])
            c.execute(insert(demand_observations), [{"variant_id": vid, "warehouse_id": 1, "day": d, "demand_qty": 1, "censored": False, "lineage": "x"}
                                                    for d in days[:10]])
        assert [s.variant_id for s in load_series(c, END)] == [9000001]
        compute_segments(c, through_day=END)
        assert {r.variant_id for r in c.execute(select(product_segments)).all()} == {9000001}


def test_exports_for_forecasting_and_proposals_leave_services_out(client, engine):
    apply(engine)
    body = client.get("/export/stock", headers=auth()).json()
    assert [v["variant_id"] for v in body["variants"]] == [9000001] and body["count"] == 1


def test_a_service_does_not_raise_the_missing_vat_data_quality_risk(engine):
    from risk.daily import evaluate_risks

    apply(engine)
    with engine.begin() as c:
        c.execute(products.update().values(vat_rate=None))
        risks = evaluate_risks(c, as_of=END)
    flagged = {r["variant_id"] for r in risks if r.get("risk_type") == "data_quality"}
    assert 9000001 in flagged and 9000002 not in flagged


def test_money_stays_decimal(engine):
    apply(engine)
    with engine.connect() as c:
        assert c.execute(select(variants.c.price).where(variants.c.external_id == 9000002)).scalar_one() == Decimal("30")
