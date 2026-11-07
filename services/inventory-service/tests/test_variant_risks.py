"""T178 (US2/AC4): the product detail carries the product's own risk reasons, from the same rules as the risk list."""

from conftest import auth
from db.tables import variants
from sqlalchemy import insert


def risk(v, kind, key):
    return {"variant_id": v, "risk_type": kind, "explanation_key": key, "params": {"sku": f"SYN-{v}"}}


def test_the_detail_lists_only_this_products_risks(client, engine, monkeypatch):
    from api import routes

    with engine.begin() as c:
        c.execute(insert(variants).values([{"external_id": 1, "sku": "SYN-1", "name": "V1", "pack_size": 1, "uom": "u"},
                                           {"external_id": 2, "sku": "SYN-2", "name": "V2", "pack_size": 1, "uom": "u"}]))
    monkeypatch.setattr(routes, "evaluate_risks", lambda conn, **kw: [risk(1, "stockout", "risk.stockout.imminent"), risk(2, "expiry", "risk.expiry.soon"), risk(1, "expiry", "risk.expiry.soon")])
    body = client.get("/variants/1", headers=auth()).json()
    assert [(r["risk_type"], r["explanation_key"]) for r in body["risks"]] == [("stockout", "risk.stockout.imminent"), ("expiry", "risk.expiry.soon")]
    assert body["risks"][0]["params"] == {"sku": "SYN-1"}
    assert client.get("/variants/2", headers=auth()).json()["risks"] == [{"risk_type": "expiry", "explanation_key": "risk.expiry.soon", "params": {"sku": "SYN-2"}}]


def test_a_product_without_risks_has_an_empty_list(client, engine, monkeypatch):
    from api import routes

    with engine.begin() as c:
        c.execute(insert(variants).values(external_id=3, sku="SYN-3", name="V3", pack_size=1, uom="u"))
    monkeypatch.setattr(routes, "evaluate_risks", lambda conn, **kw: [])
    assert client.get("/variants/3", headers=auth()).json()["risks"] == []
