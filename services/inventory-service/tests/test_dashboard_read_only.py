"""Feature 014 (T053, 006 FR-020): the inventory dashboard routes are read-only: GET only, and a request changes nothing in the database."""

from conftest import auth
from db.tables import metadata
from reference_dataset import freeze_clock, seed_reference
from sqlalchemy import func, select

HTTP = ("get", "post", "put", "patch", "delete")
TABLES = ("variants", "stock_lots", "stock_snapshots", "demand_observations", "lot_cost_projection", "agg_daily_kpis", "audit_events")


def test_every_dashboard_route_accepts_get_only(client):
    ops = [(m, p) for p, o in client.app.openapi()["paths"].items() if p.startswith("/dashboard") for m in o if m in HTTP]
    assert len(ops) >= 8 and {m for m, _p in ops} == {"get"}, ops


def test_reading_every_dashboard_view_changes_no_row(client, engine, monkeypatch):
    freeze_clock(monkeypatch)
    seed_reference(engine)

    def counts():
        with engine.connect() as c:
            return {t: c.execute(select(func.count()).select_from(metadata.tables[t])).scalar_one() for t in TABLES}

    before = counts()
    for path in ("/dashboard/summary", "/dashboard/indicators", "/dashboard/charts", "/dashboard/freshness", "/dashboard/filters/options", "/dashboard/skus/SYN-001",
                 "/dashboard/drilldown?kind=inventory_value", "/dashboard/export?kind=cards", "/dashboard/abc-xyz", "/dashboard/demand-trend"):
        assert client.get(path, headers=auth("buyer")).status_code == 200, path
    assert counts() == before


def test_a_write_verb_on_a_dashboard_route_is_refused(client):
    for verb in ("post", "put", "patch", "delete"):
        assert getattr(client, verb)("/dashboard/summary", headers=auth("buyer")).status_code == 405
