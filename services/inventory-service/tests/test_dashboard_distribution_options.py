"""T031 / T032 (feature 006): the ABC/XYZ distribution follows the filters its data can follow and names the ones it cannot; the filter options list suppliers and the data range.

Synthetic reference dataset (TOTALS.md): segments A/X (1), B/Y (2, 3, 5), C/Z (4); lots costed by sup-a and sup-b; demand from 2026-08-12.
"""

import pytest
from conftest import auth
from reference_dataset import seed_reference


@pytest.fixture
def seeded(engine):
    seed_reference(engine)
    return engine


def cells(client, query="", role="buyer"):
    return client.get(f"/dashboard/abc-xyz{query}", headers=auth(role))


def total(res):
    return sum(c["variant_count"] for c in res.json()["cells"])


def test_without_filters_nothing_is_unsupported(client, seeded):
    res = cells(client)
    assert res.status_code == 200 and total(res) == 5 and res.json()["filters_unsupported"] == []


def test_category_and_supplier_narrow_the_cells(client, seeded):
    assert {(c["abc"], c["xyz"]) for c in cells(client, "?category=A").json()["cells"]} == {("A", "X")}
    sup = total(cells(client, "?supplier_id=sup-a"))
    assert 0 < sup < 5 and total(cells(client, "?supplier_id=nobody")) == 0


def test_warehouse_and_the_date_range_are_named_as_unsupported_and_not_applied(client, seeded):
    res = cells(client, "?warehouse_id=2&date_from=2026-10-01&date_to=2026-10-12")
    assert res.status_code == 200 and total(res) == 5 and res.json()["filters_unsupported"] == ["warehouse", "date_range"]


def test_bad_values_are_refused(client, seeded):
    for q in ("?category=Z", "?supplier_id=" + "a" * 40, "?date_from=nope", "?warehouse_id=-1"):
        assert cells(client, q).status_code == 422, q


def test_a_viewer_still_gets_no_money_from_the_filtered_distribution(client, seeded):
    assert all(not c.get("value") for c in cells(client, "?supplier_id=sup-a", "viewer").json()["cells"])


def test_options_list_the_suppliers_with_cost_data_and_the_data_range(client, seeded):
    r = client.get("/dashboard/filters/options", headers=auth()).json()
    assert [s["id"] for s in r["suppliers"]] == ["sup-a", "sup-b"]
    assert r["data_range"]["from"] == "2026-08-12" and r["data_range"]["to"] >= r["data_range"]["from"]


def test_an_empty_database_has_no_suppliers_and_no_range(client):
    r = client.get("/dashboard/filters/options", headers=auth()).json()
    assert r["suppliers"] == [] and r["data_range"] is None
