"""T076: clinical criticality is editable in the policy console, by SKU, audited, refused for viewers."""

from conftest import auth
from db.tables import audit_events, products, variants
from sqlalchemy import insert, select


def seed(engine):
    with engine.begin() as c:
        c.execute(insert(products).values(external_id=5, name="Producto Sintético", status="active", missed_syncs=0))
        c.execute(insert(variants).values(external_id=1, product_id=5, sku="SYN-1", name="V", pack_size=1, uom="unit"))


def test_the_console_lists_products_with_their_manual_flag_and_sku(client, engine):
    seed(engine)
    assert client.get("/criticality", headers=auth()).json()["products"] == [{"sku": "SYN-1", "name": "Producto Sintético", "clinical_critical": False, "variants": 1}]


def test_a_buyer_changes_it_by_sku_and_the_change_is_audited(client, engine):
    seed(engine)
    assert client.put("/products/syn-1/criticality", json={"critical": True}, headers=auth("buyer")).json() == {"sku": "SYN-1", "clinical_critical": True, "changed": True}
    assert client.get("/criticality", headers=auth()).json()["products"][0]["clinical_critical"] is True
    assert client.put("/products/SYN-1/criticality", json={"critical": True}, headers=auth("buyer")).json()["changed"] is False
    with engine.connect() as c:
        events = c.execute(select(audit_events).where(audit_events.c.action == "criticality.changed")).all()
    assert len(events) == 1 and events[0].actor == "user-buyer"


def test_a_viewer_is_refused_and_unknown_or_ambiguous_skus_are_refused(client, engine):
    seed(engine)
    with engine.begin() as c:
        c.execute(insert(products).values(external_id=6, name="Otro", status="active", missed_syncs=0))
        c.execute(insert(variants).values(external_id=2, product_id=6, sku="dup", name="V", pack_size=1, uom="unit"))
        c.execute(insert(variants).values(external_id=3, product_id=6, sku="DUP ", name="V", pack_size=1, uom="unit"))
    assert client.put("/products/SYN-1/criticality", json={"critical": True}, headers=auth("viewer")).status_code == 403
    assert client.put("/products/SYN-9/criticality", json={"critical": True}, headers=auth("buyer")).json()["detail"] == "sku_unknown"
    assert client.put("/products/DUP/criticality", json={"critical": True}, headers=auth("buyer")).json()["detail"] == "sku_ambiguous"
    assert client.get("/criticality", headers=auth()).json()["products"][0]["clinical_critical"] is False
