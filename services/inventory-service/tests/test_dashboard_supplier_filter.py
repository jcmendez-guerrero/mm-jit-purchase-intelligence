"""T010: the supplier filter on stock figures uses the supplier of each lot's cost; expected values are in TOTALS.md."""

from decimal import Decimal

from dashboard.kpis import Filters, compute_summary
from reference_dataset import TODAY, seed_reference

D = Decimal


def test_supplier_totals_match_the_documented_expectation(engine):
    seed_reference(engine)
    with engine.connect() as c:
        a = compute_summary(c, TODAY, Filters(supplier_id="sup-a"))
        b = compute_summary(c, TODAY, Filters(supplier_id="sup-b"))
    assert (a.inventory_value, a.expiring_value, a.valued_with_estimate, a.unvalued_lots) == (D("42"), D("20"), 0, 0)
    assert (b.inventory_value, b.expiring_value, b.valued_with_estimate, b.unvalued_lots) == (D("58"), D("40"), 1, 0)


def test_supplier_and_warehouse_combine(engine):
    seed_reference(engine)
    with engine.connect() as c:
        s = compute_summary(c, TODAY, Filters(warehouse_id=2, supplier_id="sup-b"))
    assert s.inventory_value == D("40") and s.expiring_value == D("40")


def test_an_unknown_supplier_gives_empty_figures_not_the_whole_stock(engine):
    seed_reference(engine)
    with engine.connect() as c:
        s = compute_summary(c, TODAY, Filters(supplier_id="nobody"))
    assert s.inventory_value == D("0") and s.variant_count == 0


def test_the_api_applies_the_supplier_filter_and_refuses_a_hostile_one(client, engine):
    from conftest import auth

    seed_reference(engine)
    ok = client.get("/dashboard/summary?supplier_id=sup-a", headers=auth("buyer"))
    assert ok.status_code == 200 and ok.json()["inventory_value"] == "42.00"
    bad = client.get("/dashboard/summary", params={"supplier_id": "x'; DROP TABLE variants;--"}, headers=auth("buyer"))
    assert bad.status_code == 422


def test_every_figure_uses_the_same_supplier_scope(engine):
    """SYN-005 has stock from both suppliers, so it is in both; SYN-004 only has an old sup-a cost row with no stock, so it is not in sup-a."""
    from dashboard.kpis import variant_scope

    seed_reference(engine)
    with engine.connect() as c:
        a, b = variant_scope(c, Filters(supplier_id="sup-a")), variant_scope(c, Filters(supplier_id="sup-b"))
    assert a == {1, 5} and b == {2, 4, 5}
