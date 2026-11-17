"""Feature 014 (T092, FR-008a): every row procurement-service sends towards the browser that names a product carries its SKU next to the internal id (the gateway drops the id)."""

from conftest import add_product
from db.tables import product_refs
from sku_labels import with_skus
from sqlalchemy import update


def test_every_dict_with_an_internal_id_gets_the_sku_at_any_depth(conn):
    add_product(conn, 1, 10)
    add_product(conn, 2, 20)
    conn.execute(update(product_refs).where(product_refs.c.variant_id == 1).values(sku=" SYN-001 ", name="Uno"))
    conn.execute(update(product_refs).where(product_refs.c.variant_id == 2).values(sku="SYN-002", name="Dos"))
    out = with_skus(conn, {"lines": [{"variant_id": 1, "qty": 3}, {"variant_id": 2}], "changes": [{"variant_id": 9, "qty": 1}], "n": {"variant_id": None}})
    assert out["lines"][0] == {"variant_id": 1, "qty": 3, "sku": "SYN-001"} and out["lines"][1]["sku"] == "SYN-002"
    assert out["changes"][0]["sku"] is None and out["changes"][0]["sku_missing"] is True      # unknown is flagged for review, never guessed
    assert "sku_missing" not in out["lines"][0]
    assert "sku" not in out["n"]                                # no id, nothing to add


def test_a_list_and_an_existing_sku_are_left_alone(conn):
    add_product(conn, 1, 10)
    conn.execute(update(product_refs).where(product_refs.c.variant_id == 1).values(sku="SYN-001"))
    assert with_skus(conn, [{"variant_id": 1, "sku": "KEEP"}]) == [{"variant_id": 1, "sku": "KEEP"}]
    assert with_skus(conn, [{"variant_id": 1}]) == [{"variant_id": 1, "sku": "SYN-001"}]
