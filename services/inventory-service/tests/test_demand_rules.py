"""T075: demand exclusions and censoring rules change the forecast inputs and are reversible (feature 011: by SKU, pick-list reasons, revisions)."""

from datetime import date

from conftest import auth
from db.tables import audit_events, demand_observations, products, variants
from demand.rebuild import rebuild
from sqlalchemy import insert, select
from test_review_and_metrics import T, add, snapshot

BODY = {"sku": "SYN-1", "from_day": "2026-10-03", "to_day": "2026-10-03", "reason_code": "promotion"}


def seed(engine):
    add(engine, 1, "initial_stock", 20, T(1))
    for i, day in enumerate((2, 3, 4)):
        add(engine, 10 + i, "sale_shipment", -2, T(day))
    snapshot(engine, 1, date(2026, 10, 6), 14)
    with engine.begin() as c:
        c.execute(insert(products).values(external_id=5, name="Producto Sintético", status="active", missed_syncs=0))
        c.execute(insert(variants).values(external_id=1, product_id=5, sku="SYN-1", name="V", pack_size=1, uom="unit"))
        rebuild(c)


def flags(engine):
    with engine.connect() as c:
        return {r.day.day: bool(r.censored) for r in c.execute(select(demand_observations).where(demand_observations.c.variant_id == 1)).all()}


def test_an_exclusion_marks_its_days_unobservable_and_deactivating_restores_them(client, engine):
    seed(engine)
    assert not any(flags(engine).values())
    r = client.post("/demand-rules/exclusions", json=BODY, headers=auth("buyer"))
    assert r.status_code == 201
    assert flags(engine) == {2: False, 3: True, 4: False}
    off = client.put(f"/demand-rules/exclusions/{r.json()['id']}", json={"active": False}, headers={**auth("buyer"), "If-Match": '"1"'})
    assert off.json()["active"] is False
    assert not any(flags(engine).values())                                                 # reversible: the day counts again
    listed = client.get("/demand-rules", headers=auth()).json()["exclusions"][0]
    assert listed["active"] is False and listed["sku"] == "SYN-1" and "variant_id" not in listed     # never deleted; people see the SKU


def test_an_exclusion_for_all_products_applies_to_every_variant(client, engine):
    seed(engine)
    client.post("/demand-rules/exclusions", json={"from_day": "2026-10-02", "to_day": "2026-10-04", "reason_code": "closure"}, headers=auth("buyer"))
    assert all(flags(engine).values())


def test_validation_roles_and_audit(client, engine):
    seed(engine)
    assert client.post("/demand-rules/exclusions", json=BODY, headers=auth("viewer")).status_code == 403
    assert client.post("/demand-rules/exclusions", json={**BODY, "to_day": "2026-10-01"}, headers=auth("buyer")).json()["detail"] == "policy_out_of_range"
    assert client.post("/demand-rules/exclusions", json={**BODY, "from_day": "2001-01-01"}, headers=auth("buyer")).json()["detail"] == "import_date_out_of_range"
    assert client.post("/demand-rules/exclusions", json={**BODY, "reason_code": "free text"}, headers=auth("buyer")).json()["detail"] == "exclusion_reason_invalid"
    assert client.post("/demand-rules/exclusions", json={**BODY, "detail": "x" * 101}, headers=auth("buyer")).json()["detail"] == "exclusion_reason_invalid"
    assert client.post("/demand-rules/exclusions", json={**BODY, "sku": "NOPE"}, headers=auth("buyer")).json()["detail"] == "sku_unknown"
    assert client.put("/demand-rules/exclusions/99", json={"active": False}, headers={**auth("buyer"), "If-Match": '"1"'}).status_code == 404
    client.post("/demand-rules/exclusions", json={**BODY, "detail": "campaña de otoño"}, headers=auth("buyer"))
    with engine.connect() as c:
        events = c.execute(select(audit_events)).all()
    assert [a.action for a in events] == ["demand_exclusion.added"]
    assert events[0].after["reason_code"] == "promotion" and "campaña" not in str(events[0].after)      # free-text detail never reaches the audit


def test_the_detail_is_shown_to_admins_only(client, engine):
    seed(engine)
    client.post("/demand-rules/exclusions", json={**BODY, "detail": "campaña de otoño"}, headers=auth("buyer"))
    assert "detail" not in client.get("/demand-rules", headers=auth("buyer")).json()["exclusions"][0]
    assert client.get("/demand-rules", headers=auth("admin")).json()["exclusions"][0]["detail"] == "campaña de otoño"


def test_the_censoring_rule_replaces_a_fixed_constant(client, engine):
    """A single zero-stock day is hidden demand by default; with min_zero_stock_days=3 it is not."""
    add(engine, 1, "initial_stock", 4, T(1))
    add(engine, 2, "sale_shipment", -4, T(2))              # stock hits zero on day 2
    add(engine, 3, "purchase_receipt", 6, T(4))             # restocked on day 4
    snapshot(engine, 1, date(2026, 10, 6), 6)
    with engine.begin() as c:
        rebuild(c)
    from db.tables import stock_history

    def censored_days():
        with engine.connect() as c:
            return sorted(r.day.day for r in c.execute(select(stock_history).where(stock_history.c.censored)).all())

    rule = "/demand-rules/rules/min_zero_stock_days"
    assert censored_days() != []
    assert client.get("/demand-rules", headers=auth()).json()["rules"][0] == {"rule": "min_zero_stock_days", "value": 1, "min": 1, "max": 30, "default": 1, "revision": 0}
    assert client.put(rule, json={"value": 5}, headers=auth("buyer")).json()["revision"] == 1
    assert censored_days() == []
    assert client.put(rule, json={"value": 0}, headers={**auth("buyer"), "If-Match": '"1"'}).status_code == 422
    assert client.put("/demand-rules/rules/unknown", json={"value": 2}, headers=auth("buyer")).status_code == 422
    assert client.put(rule, json={"value": 1}, headers={**auth("buyer"), "If-Match": '"1"'}).json()["revision"] == 2
    assert censored_days() != []


def test_a_rule_change_announces_demand_updated_so_the_forecast_is_recomputed(client, engine, tmp_path):
    from db.tables import outbox
    from demand.publisher import LocalBlobWriter

    seed(engine)
    client.app.state.blob_writer = LocalBlobWriter(tmp_path)
    client.post("/demand-rules/exclusions", json=BODY, headers=auth("buyer"))
    with engine.connect() as c:
        assert [e.type for e in c.execute(select(outbox)).all()] == ["inventory.demand.updated.v1"]
