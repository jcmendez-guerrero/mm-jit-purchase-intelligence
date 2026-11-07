"""T119 (inventory side): filter options come from live data; none are hard-coded."""

from conftest import auth
from db.tables import product_segments, products, warehouses
from sqlalchemy import insert
from test_aggregates import NOW, seed


def test_options_reflect_the_data_and_nothing_else(client, engine):
    r = client.get("/dashboard/filters/options", headers=auth()).json()
    assert r == {"warehouses": [], "categories": [], "families": [], "family_available": False}                # an empty database offers nothing
    seed(engine)
    r = client.get("/dashboard/filters/options", headers=auth()).json()
    assert [w["name"] for w in r["warehouses"]] == ["Almacén sintético A", "Almacén sintético B"]
    assert [c["id"] for c in r["categories"]] == ["B", "A", "critical"] or {c["id"] for c in r["categories"]} == {"A", "B", "critical"}
    assert r["family_available"] is False and r["families"] == []                                # no product has a synchronised family yet


def test_a_new_warehouse_or_category_appears_without_any_code_change(client, engine):
    seed(engine)
    with engine.begin() as c:
        c.execute(insert(warehouses).values(external_id=9, name="Almacén sintético Z", is_unassigned=False))
        c.execute(insert(warehouses).values(external_id=10, name="Sin asignar", is_unassigned=True))
        c.execute(insert(products).values(external_id=77, name="X", status="active", missed_syncs=0))
        c.execute(insert(product_segments).values(variant_id=900, abc="C", xyz="Z", pattern="new", forecast_eligible=False, reason="new", metrics={}, computed_at=NOW, run_id="r"))
    r = client.get("/dashboard/filters/options", headers=auth()).json()
    assert "Almacén sintético Z" in [w["name"] for w in r["warehouses"]] and "Sin asignar" not in [w["name"] for w in r["warehouses"]]
    assert "C" in {c["id"] for c in r["categories"]}


def test_no_option_list_is_hard_coded_in_the_service_source():
    import pathlib

    src = (pathlib.Path(__file__).parents[1] / "src" / "dashboard" / "kpis.py").read_text()
    assert "Almac" not in src and "Principal" not in src
