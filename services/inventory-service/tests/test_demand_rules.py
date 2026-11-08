"""T075: demand exclusions and censoring rules change the forecast inputs and are reversible."""

from datetime import date

from conftest import auth
from db.tables import audit_events, demand_observations
from demand.rebuild import rebuild
from sqlalchemy import select
from test_review_and_metrics import T, add, snapshot


def seed(engine):
    add(engine, 1, "initial_stock", 20, T(1))
    for i, day in enumerate((2, 3, 4)):
        add(engine, 10 + i, "sale_shipment", -2, T(day))
    snapshot(engine, 1, date(2026, 10, 6), 14)
    with engine.begin() as c:
        rebuild(c)


def flags(engine):
    with engine.connect() as c:
        return {r.day.day: bool(r.censored) for r in c.execute(select(demand_observations).where(demand_observations.c.variant_id == 1)).all()}


def test_an_exclusion_marks_its_days_unobservable_and_deactivating_restores_them(client, engine):
    seed(engine)
    assert not any(flags(engine).values())
    r = client.post("/demand-rules/exclusions", json={"variant_id": 1, "from_day": "2026-10-03", "to_day": "2026-10-03", "reason": "promoción de otoño"}, headers=auth("buyer"))
    assert r.status_code == 201
    assert flags(engine) == {2: False, 3: True, 4: False}
    assert client.put(f"/demand-rules/exclusions/{r.json()['id']}", json={"active": False}, headers=auth("buyer")).json()["active"] is False
    assert not any(flags(engine).values())                                                 # reversible: the day counts again
    assert client.get("/demand-rules", headers=auth()).json()["exclusions"][0]["active"] is False     # never deleted


def test_an_exclusion_for_all_products_applies_to_every_variant(client, engine):
    seed(engine)
    client.post("/demand-rules/exclusions", json={"from_day": "2026-10-02", "to_day": "2026-10-04", "reason": "cierre por obras"}, headers=auth("buyer"))
    assert all(flags(engine).values())


def test_validation_roles_and_audit(client, engine):
    seed(engine)
    body = {"variant_id": 1, "from_day": "2026-10-03", "to_day": "2026-10-03", "reason": "promoción"}
    assert client.post("/demand-rules/exclusions", json=body, headers=auth("viewer")).status_code == 403
    assert client.post("/demand-rules/exclusions", json={**body, "to_day": "2026-10-01"}, headers=auth("buyer")).json()["detail"] == "policy_out_of_range"
    assert client.post("/demand-rules/exclusions", json={**body, "from_day": "2001-01-01"}, headers=auth("buyer")).json()["detail"] == "import_date_out_of_range"
    assert client.post("/demand-rules/exclusions", json={**body, "reason": " "}, headers=auth("buyer")).json()["detail"] == "override_reason_required"
    assert client.put("/demand-rules/exclusions/99", json={"active": False}, headers=auth("buyer")).status_code == 404
    client.post("/demand-rules/exclusions", json=body, headers=auth("buyer"))
    with engine.connect() as c:
        assert [a.action for a in c.execute(select(audit_events)).all()] == ["demand_exclusion.added"]


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

    assert censored_days() != []
    assert client.get("/demand-rules", headers=auth()).json()["rules"][0] == {"rule": "min_zero_stock_days", "value": 1, "min": 1, "max": 30, "default": 1}
    assert client.put("/demand-rules/rules/min_zero_stock_days", json={"value": 5}, headers=auth("buyer")).json()["revision"] == 1
    assert censored_days() == []
    assert client.put("/demand-rules/rules/min_zero_stock_days", json={"value": 0}, headers=auth("buyer")).status_code == 422
    assert client.put("/demand-rules/rules/unknown", json={"value": 2}, headers=auth("buyer")).status_code == 422
    assert client.put("/demand-rules/rules/min_zero_stock_days", json={"value": 1}, headers=auth("buyer")).json()["revision"] == 2
    assert censored_days() != []


def test_a_rule_change_announces_demand_updated_so_the_forecast_is_recomputed(client, engine, tmp_path):
    from db.tables import outbox
    from demand.publisher import LocalBlobWriter

    seed(engine)
    client.app.state.blob_writer = LocalBlobWriter(tmp_path)
    client.post("/demand-rules/exclusions", json={"variant_id": 1, "from_day": "2026-10-03", "to_day": "2026-10-03", "reason": "promoción"}, headers=auth("buyer"))
    with engine.connect() as c:
        assert [e.type for e in c.execute(select(outbox)).all()] == ["inventory.demand.updated.v1"]
