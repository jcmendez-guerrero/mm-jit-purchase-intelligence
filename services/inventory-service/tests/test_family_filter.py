"""T170 (FR-006): the ERP product family is synchronised with the variants and offered as a live filter next to the demand group."""

from datetime import date

from conftest import auth
from db.tables import products
from projections.apply import apply_payload
from sqlalchemy import select, update
from test_aggregates import seed


def families(engine, a="Familia sintética A", b="Familia sintética B"):
    with engine.begin() as c:
        c.execute(update(products).where(products.c.external_id == 5).values(family=a))
        c.execute(update(products).where(products.c.external_id == 6).values(family=b))


def test_the_sync_stores_the_family_with_the_product_and_a_sync_without_it_keeps_the_last_one(engine):
    rec = {"id": 1, "product_id": 5, "product_name": "P", "sku": "S", "name": "V", "pack_size": 1, "uom": "u", "total_on_hand": 1, "category": "Familia sintética A"}
    with engine.begin() as c:
        apply_payload(c, {"kind": "variants", "records": [rec]}, date(2026, 11, 9))
    with engine.connect() as c:
        assert c.execute(select(products.c.family)).scalar() == "Familia sintética A"
    with engine.begin() as c:
        apply_payload(c, {"kind": "variants", "records": [{k: v for k, v in rec.items() if k != "category"}]}, date(2026, 11, 10))
    with engine.connect() as c:
        assert c.execute(select(products.c.family)).scalar() == "Familia sintética A"


def test_a_family_name_is_trimmed_and_capped_and_blank_means_none(engine):
    base = {"id": 1, "product_id": 5, "product_name": "P", "sku": "S", "name": "V", "pack_size": 1, "uom": "u", "total_on_hand": 1}
    with engine.begin() as c:
        apply_payload(c, {"kind": "variants", "records": [{**base, "category": "  " + "x" * 300 + "  "}]}, date(2026, 11, 9))
    with engine.connect() as c:
        assert c.execute(select(products.c.family)).scalar() == "x" * 120
    with engine.begin() as c:
        apply_payload(c, {"kind": "variants", "records": [{**base, "category": "   "}]}, date(2026, 11, 10))
    with engine.connect() as c:
        assert c.execute(select(products.c.family)).scalar() == "x" * 120      # blank is "not given", not a reason to erase


def test_options_list_the_families_present_and_say_when_there_are_none(client, engine):
    seed(engine)
    assert client.get("/dashboard/filters/options", headers=auth()).json()["family_available"] is False
    families(engine)
    r = client.get("/dashboard/filters/options", headers=auth()).json()
    assert r["family_available"] is True and [f["id"] for f in r["families"]] == ["Familia sintética A", "Familia sintética B"]


def test_the_family_narrows_the_summary_and_combines_with_the_demand_group(client, engine):
    seed(engine)
    families(engine)
    allv = client.get("/dashboard/summary", headers=auth()).json()["variant_count"]
    a = client.get("/dashboard/summary?family=Familia sintética A", headers=auth()).json()
    b = client.get("/dashboard/summary?family=Familia sintética B", headers=auth()).json()
    assert (allv, a["variant_count"], b["variant_count"]) == (3, 2, 1)
    both = client.get("/dashboard/summary?family=Familia sintética A&category=A", headers=auth()).json()
    assert both["variant_count"] == 1
    none = client.get("/dashboard/summary?family=Otra", headers=auth()).json()
    assert none["variant_count"] == 0                                    # an unknown family is an empty selection, not an error


def test_a_family_filter_is_validated(client):
    assert client.get("/dashboard/summary?family=" + "x" * 121, headers=auth()).status_code == 422
