"""T095 (FR-037, R16): export costs are a reference refreshed on every load, reachable only by the local loader."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from api import costs
from api.internal_export_costs import build_router, enabled
from db.tables import export_costs
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from sqlalchemy import func, select
from suppliers.export_costs import get_export_cost, upsert_export_costs

NOW = datetime(2026, 11, 8, 12, tzinfo=UTC)


class Roles:
    def validate(self, token, required_roles=()):
        roles = {"loader": {"local-loader"}, "viewer": {"viewer"}}.get(token, set())
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(subject=f"svc-{token}", roles=frozenset(roles), auth_time=None)


def h(role):
    return {"Authorization": f"Bearer {role}"}


@pytest.fixture
def app_client(engine):
    app = create_service_app("procurement-service", validator=Roles())
    app.include_router(build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app)


def row(sku="SYN-000001", cost="5.50", pvp="12.10"):
    return {"sku": sku, "export_cost": cost, "pvp_gross": pvp, "tax_rate": "21", "tax_included": False, "currency": "EUR"}


def test_enabled_only_for_the_local_loader_outside_cloud_environments():
    assert enabled({"MMI_LOCAL_LOADER": "1", "MMI_ENV": "dev"})
    assert not enabled({"MMI_ENV": "dev"})
    assert not enabled({"MMI_LOCAL_LOADER": "1", "MMI_ENV": "prod"}) and not enabled({"MMI_LOCAL_LOADER": "1", "MMI_ENV": "staging"})


def test_the_endpoint_needs_the_loader_identity(app_client):
    body = {"rows": [row()]}
    assert app_client.post("/internal/export-costs", json=body).status_code == 401
    assert app_client.post("/internal/export-costs", json=body, headers=h("viewer")).status_code == 403
    assert app_client.post("/internal/export-costs", json=body, headers=h("loader")).status_code == 200


def test_rows_are_stored_with_exact_decimals(app_client, engine):
    r = app_client.post("/internal/export-costs", json={"load_run_id": "run-1", "rows": [row(), row("SYN-000002", None, "3.00")]}, headers=h("loader"))
    assert r.json() == {"upserted": 2}
    with engine.connect() as c:
        got = {x.sku: x for x in c.execute(select(export_costs)).all()}
    assert got["SYN-000001"].export_cost == Decimal("5.50") and got["SYN-000001"].pvp_gross == Decimal("12.10") and got["SYN-000001"].load_run_id == "run-1"
    assert got["SYN-000002"].export_cost is None


def test_a_reload_refreshes_the_reference_without_duplicates(app_client, engine):
    app_client.post("/internal/export-costs", json={"rows": [row(cost="5.50")]}, headers=h("loader"))
    app_client.post("/internal/export-costs", json={"rows": [row(sku="syn-000001", cost="6.25")]}, headers=h("loader"))
    with engine.connect() as c:
        assert c.execute(select(func.count()).select_from(export_costs)).scalar_one() == 1
        assert get_export_cost(c, "SYN-000001")["export_cost"] == Decimal("6.25")


@pytest.mark.parametrize("bad", [
    {**row(), "export_cost": "-1"}, {**row(), "export_cost": 5.5}, {**row(), "pvp_gross": "abc"}, {**row(), "sku": ""},
    {**row(), "sku": "x" * 61}, {**row(), "currency": "euro"}, {**row(), "unexpected": "x"},
])
def test_invalid_rows_are_refused(app_client, bad):
    assert app_client.post("/internal/export-costs", json={"rows": [bad]}, headers=h("loader")).status_code == 422


def test_lookup_ignores_case_and_returns_none_for_unknown(engine):
    with engine.begin() as c:
        upsert_export_costs(c, [{"sku": "SYN-000009", "export_cost": Decimal("1.00"), "pvp_gross": None, "tax_rate": None,
                                 "tax_included": False, "currency": "EUR"}], "run", NOW)
        assert get_export_cost(c, " syn-000009 ")["export_cost"] == Decimal("1.00")
        assert get_export_cost(c, "SYN-404") is None


def test_the_route_is_absent_when_not_included(engine):
    app = create_service_app("procurement-service", validator=Roles())
    assert TestClient(app).post("/internal/export-costs", json={"rows": []}, headers=h("loader")).status_code == 404
