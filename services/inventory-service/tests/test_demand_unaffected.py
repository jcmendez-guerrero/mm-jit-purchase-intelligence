"""T102: imported predictive data never appears in the ERP-derived demand series. Inventory has no import path; its series come only from stock movements."""

from datetime import date

from db.tables import demand_observations, stock_movements
from demand.rebuild import rebuild
from sqlalchemy import func, select
from test_review_and_metrics import T, add, snapshot


def test_every_demand_row_comes_from_an_erp_sale_movement_and_the_service_has_no_import_module():
    import importlib.util

    assert importlib.util.find_spec("seeds") is None                       # seed handling lives in forecast-service only


def test_demand_equals_the_sales_movements_nothing_more(engine):
    add(engine, 1, "initial_stock", 20, T(1))
    add(engine, 2, "sale_shipment", -3, T(2))
    add(engine, 3, "sale_shipment", -2, T(3))
    snapshot(engine, 1, date(2026, 10, 6), 15)
    with engine.begin() as c:
        rebuild(c)
        total = c.execute(select(func.sum(demand_observations.c.demand_qty))).scalar()
        sales = -c.execute(select(func.sum(stock_movements.c.quantity)).where(stock_movements.c.reason == "sale_shipment")).scalar()
    assert total == sales == 5
