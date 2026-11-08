"""T076: clinical criticality is editable in the policy console through the existing endpoint, audited, refused for viewers."""

from conftest import auth
from db.tables import audit_events, products, variants
from sqlalchemy import insert, select


def seed(engine):
    with engine.begin() as c:
        c.execute(insert(products).values(external_id=5, name="Producto Sintético", status="active", missed_syncs=0))
        c.execute(insert(variants).values(external_id=1, product_id=5, sku="SYN-1", name="V", pack_size=1, uom="unit"))


def test_the_console_lists_products_with_their_manual_flag(client, engine):
    seed(engine)
    assert client.get("/criticality", headers=auth()).json()["products"] == [{"product_id": 5, "name": "Producto Sintético", "clinical_critical": False, "variants": 1}]


def test_a_buyer_changes_it_and_the_change_is_audited(client, engine):
    seed(engine)
    assert client.put("/products/5/criticality", json={"critical": True}, headers=auth("buyer")).json()["changed"] is True
    assert client.get("/criticality", headers=auth()).json()["products"][0]["clinical_critical"] is True
    assert client.put("/products/5/criticality", json={"critical": True}, headers=auth("buyer")).json()["changed"] is False
    with engine.connect() as c:
        events = c.execute(select(audit_events).where(audit_events.c.action == "criticality.changed")).all()
    assert len(events) == 1 and events[0].actor == "user-buyer"


def test_a_viewer_is_refused_and_unknown_products_are_404(client, engine):
    seed(engine)
    assert client.put("/products/5/criticality", json={"critical": True}, headers=auth("viewer")).status_code == 403
    assert client.put("/products/99/criticality", json={"critical": True}, headers=auth("buyer")).status_code == 404
    assert client.get("/criticality", headers=auth()).json()["products"][0]["clinical_critical"] is False
