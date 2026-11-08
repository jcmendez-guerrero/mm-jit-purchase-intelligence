"""T059 (FR-033): when the inventory export names a supplier, link only on an exact single match; everything else goes to review, nothing is guessed."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from api import costs
from api.internal_import import build_router
from conftest import NOW
from costs.recargo import load_table
from costs.rules import CostRules
from db.tables import export_costs, supplier_costs, supplier_review_items
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from sqlalchemy import insert, select
from suppliers.links import auto_link
from suppliers.service import SupplierInput, create_supplier, deactivate_supplier, update_supplier
from suppliers_support import make_ref

D = Decimal


def supplier(conn, name, **kw):
    return create_supplier(conn, SupplierInput(name=name, fiscal_type="national", country="ES", currency="EUR", **kw), "buyer-1", confirm_duplicate=True, now=NOW)


def catalogue(conn, n=3):
    for i in range(1, n + 1):
        make_ref(conn, i, 100 + i, f"SYN-{i:06d}", vat=D("21"))
        conn.execute(insert(export_costs).values(sku=f"SYN-{i:06d}", export_cost=D("2.00"), pvp_gross=D("4"), tax_rate=D("21"), tax_included=False, currency="EUR", loaded_at=NOW))


def run(conn, rows):
    return auto_link(conn, rows, "svc-loader", CostRules(), load_table(conn), now=NOW)


def reviews(conn):
    return [(i.kind, i.supplier_id is not None, i.status) for i in conn.execute(select(supplier_review_items)).all()]


def test_an_exact_single_match_links_with_the_export_cost(conn):
    catalogue(conn)
    s = supplier(conn, "Proveedor Alfa S.L.")
    out = run(conn, [{"sku": "SYN-000001", "supplier_name": "PROVEEDOR ALFA SL"}])
    assert out["linked"] == 1
    c = conn.execute(select(supplier_costs)).one()
    assert (c.supplier_id, c.source, c.cost_with_recargo) == (s.id, "inventory_export", D("2.1040"))
    assert reviews(conn) == []


def test_no_match_goes_to_review_without_the_supplier_name(conn):
    catalogue(conn)
    out = run(conn, [{"sku": "SYN-000001", "supplier_name": "Proveedor Inexistente"}])
    assert out["no_match"] == 1 and conn.execute(select(supplier_costs)).all() == []
    item = conn.execute(select(supplier_review_items)).one()
    assert (item.kind, item.supplier_id) == ("link_no_match", None) and "Inexistente" not in item.detail and "SYN-000001" in item.detail


def test_several_matches_are_ambiguous_and_nothing_is_linked(conn):
    catalogue(conn)
    supplier(conn, "Repetido SL")
    supplier(conn, "REPETIDO S.L.")
    out = run(conn, [{"sku": "SYN-000001", "supplier_name": "repetido s.l"}])
    assert out["ambiguous"] == 1 and out["linked"] == 0 and conn.execute(select(supplier_costs)).all() == []
    assert [i.kind for i in conn.execute(select(supplier_review_items)).all() if i.kind == "link_ambiguous"] == ["link_ambiguous"]


@pytest.mark.parametrize("how", ["deactivated", "non_purchasing"])
def test_a_deactivated_or_non_purchasing_match_is_reviewed_not_linked(conn, how):
    catalogue(conn)
    s = supplier(conn, "Proveedor Beta")
    if how == "deactivated":
        deactivate_supplier(conn, s.id, "b", confirm=True, now=NOW)
    else:
        update_supplier(conn, s.id, {"classification": "non_purchasing"}, "b", 1, now=NOW)
    out = run(conn, [{"sku": "SYN-000001", "supplier_name": "Proveedor Beta"}])
    assert out["inactive"] == 1 and conn.execute(select(supplier_costs)).all() == []
    assert ("link_inactive_supplier", True, "open") in reviews(conn)


def test_a_second_run_keeps_existing_links_and_does_not_repeat_review_items(conn):
    catalogue(conn)
    supplier(conn, "Proveedor Alfa")
    rows = [{"sku": "SYN-000001", "supplier_name": "Proveedor Alfa"}, {"sku": "SYN-000002", "supplier_name": "Nadie"}]
    run(conn, rows)
    again = run(conn, rows)
    assert (again["linked"], again["existing"], again["no_match"]) == (0, 1, 1)
    assert len(conn.execute(select(supplier_costs)).all()) == 1 and [k for k, *_ in reviews(conn)] == ["link_no_match"]


def test_an_unknown_sku_waits_for_the_product_references_and_is_not_reviewed(conn):
    supplier(conn, "Proveedor Alfa")
    out = run(conn, [{"sku": "SYN-404", "supplier_name": "Proveedor Alfa"}])
    assert out["sku_unknown"] == 1 and reviews(conn) == []


def test_a_product_without_any_usable_cost_is_counted(conn):
    make_ref(conn, 1, 101, "SYN-000001")
    supplier(conn, "Proveedor Alfa")
    out = run(conn, [{"sku": "SYN-000001", "supplier_name": "Proveedor Alfa"}])
    assert out["no_cost"] == 1 and out["linked"] == 0


def test_blank_supplier_names_are_skipped_silently(conn):
    catalogue(conn)
    out = run(conn, [{"sku": "SYN-000001", "supplier_name": "  "}])
    assert sum(out.values()) == 0 and reviews(conn) == []


class Roles:
    def validate(self, token, required_roles=()):
        roles = {"loader": {"local-loader"}, "viewer": {"viewer"}}.get(token, set())
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(subject="svc-loader", roles=frozenset(roles), auth_time=datetime.now(UTC))


def test_the_endpoint_links_for_the_loader_only(engine):
    with engine.begin() as c:
        catalogue(c)
        supplier(c, "Proveedor Alfa")
    app = create_service_app("procurement-service", validator=Roles())
    app.include_router(build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    client = TestClient(app)
    body = {"rows": [{"sku": "SYN-000001", "supplier_name": "Proveedor Alfa"}]}
    assert client.post("/internal/links/auto", json=body).status_code == 401
    assert client.post("/internal/links/auto", json=body, headers={"Authorization": "Bearer viewer"}).status_code == 403
    r = client.post("/internal/links/auto", json=body, headers={"Authorization": "Bearer loader"})
    assert r.status_code == 200 and r.json()["linked"] == 1
    assert client.post("/internal/links/auto", json={"rows": [{"sku": "x", "supplier_name": "y", "cif": "1"}]}, headers={"Authorization": "Bearer loader"}).status_code == 422
