"""FR-017 (T012/T023): roles that may not see costs get counts and quantities from the dashboard routes, never money. Test tokens: viewer, buyer, admin (conftest)."""

import pytest
from conftest import auth
from dashboard.kpis import refresh_aggregates
from reference_dataset import NOW, TODAY, seed_reference

MONEY = ("inventory_value", "expiring_value")


@pytest.fixture
def seeded(engine):
    seed_reference(engine)
    with engine.begin() as c:
        refresh_aggregates(c, TODAY, None, NOW)
    return engine


def test_a_viewer_gets_counts_but_no_money_from_the_summary(client, seeded):
    body = client.get("/dashboard/summary", headers=auth("viewer")).json()
    assert not any(k in body for k in MONEY) and body["hidden_by_role"] == list(MONEY)
    assert body["stockout_risk"] >= 0 and body["unvalued_lots"] == 1 and body["valued_with_estimate"] == 1 and body["variant_count"] == 5


@pytest.mark.parametrize("role", ["buyer", "admin"])
def test_buyer_and_admin_see_the_money(client, seeded, role):
    body = client.get("/dashboard/summary", headers=auth(role)).json()
    assert body["inventory_value"] == "100.00" and body["expiring_value"] == "60.00" and "hidden_by_role" not in body


def test_a_viewer_gets_the_abc_xyz_groups_without_their_value(client, seeded):
    cells = client.get("/dashboard/abc-xyz", headers=auth("viewer")).json()["cells"]
    assert cells and all("value" not in c and c["variant_count"] > 0 for c in cells)
    assert all(c["value"] for c in client.get("/dashboard/abc-xyz", headers=auth("buyer")).json()["cells"])


def test_a_viewer_gets_the_products_behind_a_money_figure_but_not_the_amounts(client, seeded):
    for kind, extra in (("inventory_value", ""), ("abc_xyz", "&abc=A&xyz=X")):
        page = client.get(f"/dashboard/drilldown?kind={kind}{extra}", headers=auth("viewer")).json()
        assert page["rows"] and page["sum"] is None and all(r["figure"] is None and r["sku"] for r in page["rows"])
        full = client.get(f"/dashboard/drilldown?kind={kind}{extra}", headers=auth("buyer")).json()
        assert full["sum"] is not None and all(r["figure"] is not None for r in full["rows"])


def test_a_viewer_keeps_the_figures_that_are_not_money(client, seeded):
    coverage = client.get("/dashboard/drilldown?kind=coverage", headers=auth("viewer")).json()
    assert coverage["rows"] and all(r["figure"] is not None for r in coverage["rows"])
