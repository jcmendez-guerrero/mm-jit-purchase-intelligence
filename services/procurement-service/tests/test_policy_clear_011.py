"""Feature 011 (T043, T044): removing an override writes a new revision that restores the lower scope or the default; orphaned product policies are flagged, never dropped."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from api import costs, policies
from db.tables import audit_events, policy_sets, product_refs
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from policies.service import (
    PolicyConflict,
    PolicyError,
    PolicyValues,
    clear_policy,
    effective_view,
    history,
    save_policy,
)
from sqlalchemy import delete, insert, select

D = Decimal
TODAY = date(2026, 11, 9)
ROLES = {"buyer": {"viewer", "buyer"}, "viewer": {"viewer"}}


def save(conn, scope, key, expected=None, **kw):
    return save_policy(conn, scope, key, PolicyValues(**kw), "buyer-1", expected_revision=expected, today=TODAY)


def test_clearing_an_override_restores_the_lower_scope_and_keeps_every_revision(conn):
    save(conn, "global", "*", min_units=5)
    save(conn, "product", "7", min_units=20)
    assert effective_view(conn, 7, (), TODAY)["min_units"]["source"] == "product"
    assert clear_policy(conn, "product", "7", "buyer-1", expected_revision=1, today=TODAY) == 2
    view = effective_view(conn, 7, (), TODAY)["min_units"]
    assert view["source"] == "global" and view["value"] == "5"
    rows = history(conn, "product", "7")
    assert [r["revision"] for r in rows] == [1, 2] and rows[0]["min_units"] == "20" and rows[1]["min_units"] is None      # the old revision is untouched
    assert "policy.cleared" in {a.action for a in conn.execute(select(audit_events)).all()}


def test_clearing_everything_returns_to_the_default(conn):
    save(conn, "global", "*", min_units=5)
    clear_policy(conn, "global", "*", "buyer-1", expected_revision=1, today=TODAY)
    assert effective_view(conn, 7, (), TODAY)["min_units"]["source"] == "default"


def test_clearing_needs_the_current_revision_and_something_to_clear(conn):
    save(conn, "global", "*", min_units=5)
    with pytest.raises(PolicyConflict):
        clear_policy(conn, "global", "*", "buyer-1", expected_revision=9, today=TODAY)
    with pytest.raises(PolicyError):
        clear_policy(conn, "segment", "A", "buyer-1", expected_revision=0, today=TODAY)
    assert conn.execute(select(policy_sets)).all().__len__() == 1


class V:
    def validate(self, token, required_roles=()):
        roles = ROLES.get(token)
        if roles is None or not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(f"user-{token}", frozenset(roles), datetime.now(UTC) - timedelta(minutes=1))


def h(role, **extra):
    return {"Authorization": f"Bearer {role}", **extra}


@pytest.fixture
def api(engine):
    with engine.begin() as c:
        c.execute(insert(product_refs).values(variant_id=5, product_id=5, sku="SYN-0005", name="Producto sintético"))
    app = create_service_app("procurement-service", validator=V())
    app.include_router(costs.build_router(app))
    app.include_router(policies.build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app)


def test_the_clear_route_needs_a_buyer_and_the_revision(api):
    api.put("/policies/product/SYN-0005", json={"min_units": 3}, headers=h("buyer"))
    assert api.delete("/policies/product/SYN-0005", headers=h("viewer", **{"If-Match": '"1"'})).status_code == 403
    assert api.delete("/policies/product/SYN-0005", headers=h("buyer")).status_code == 428
    stale = api.delete("/policies/product/SYN-0005", headers=h("buyer", **{"If-Match": '"4"'}))
    assert stale.status_code == 412 and stale.json()["current_version"] == 1
    assert api.delete("/policies/product/SYN-0005", headers=h("buyer", **{"If-Match": '"1"'})).json() == {"revision": 2}
    assert api.get("/products/SYN-0005/effective-policy", headers=h("viewer")).json()["rules"]["min_units"]["source"] == "default"


def test_a_product_policy_for_a_variant_that_is_not_in_the_catalogue_is_ignored_by_calculations(conn):
    """T065: kept in the table, but it changes no proposal input and is not recorded as a version used."""
    from conftest import add_supplier
    from proposals.inputs import InputsProvider
    from test_inputs import ELIGIBLE, Src, cost, fc, stock, sv

    sa = add_supplier(conn, 1, "A")
    cost(conn, sa, 10, "1.00")
    save_policy(conn, "product", "999", PolicyValues(min_units=500), "buyer-1", today=TODAY)          # variant 999 is not in stock or in the forecast
    inputs = InputsProvider(Src(stock(sv(1, 10, on_hand=0))), Src(fc(v1=ELIGIBLE))).build(conn, TODAY)
    assert [v.variant_id for v in inputs.variants] == [1] and inputs.variants[0].min_units is None
    assert "product:999" not in inputs.policy_versions
    assert conn.execute(select(policy_sets)).all().__len__() == 1                                       # never deleted


def test_a_policy_whose_sku_left_the_catalogue_is_kept_flagged_and_listed(api, engine):
    api.put("/policies/product/SYN-0005", json={"min_units": 3}, headers=h("buyer"))
    with engine.begin() as c:
        c.execute(delete(product_refs).where(product_refs.c.variant_id == 5))
    body = api.get("/policies", headers=h("viewer")).json()
    product_rows = [p for p in body["policies"] if p["scope"] == "product"]
    assert len(product_rows) == 1 and product_rows[0]["orphaned"] is True            # kept, never dropped
    assert product_rows[0]["key"] is None and body["orphaned"] == 1                  # no ERP id is shown as a key
    with engine.connect() as c:
        assert c.execute(select(policy_sets)).all().__len__() == 1
