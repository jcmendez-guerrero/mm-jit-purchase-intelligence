"""T058 (FR-019): the internal supplier import: flag-guarded, loader identity only, idempotent by ERP contact id, nothing sensitive accepted."""

import pytest
from api import costs
from api.internal_import import build_router, enabled
from conftest import add_supplier
from db.tables import supplier_review_items, suppliers
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from sqlalchemy import select
from suppliers.import_rules import suggest_classification


class Roles:
    def validate(self, token, required_roles=()):
        roles = {"loader": {"local-loader"}, "viewer": {"viewer"}}.get(token, set())
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(subject=f"svc-{token}", roles=frozenset(roles), auth_time=None)


def h(role="loader"):
    return {"Authorization": f"Bearer {role}"}


@pytest.fixture
def client(engine):
    app = create_service_app("procurement-service", validator=Roles())
    app.include_router(build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app)


def row(ident=9100001, name="Proveedor Sintetico Uno S.L.", **kw):
    base = {"external_contact_id": ident, "name": name, "fiscal_type": "national", "country": "ES", "currency": "EUR", "payment_terms_days": 30, "terms_unparsed": False, "has_note": False}
    base.update(kw)
    return base


def post(client, rows, role="loader"):
    return client.post("/internal/suppliers/import", json={"load_run_id": "run-1", "rows": rows}, headers=h(role))


def test_enabled_only_for_the_local_loader_outside_cloud_environments():
    assert enabled({"MMI_LOCAL_LOADER": "1", "MMI_ENV": "dev"})
    assert not enabled({"MMI_ENV": "dev"}) and not enabled({"MMI_LOCAL_LOADER": "1", "MMI_ENV": "prod"}) and not enabled({"MMI_LOCAL_LOADER": "1", "MMI_ENV": "staging"})


def test_the_route_is_absent_when_not_included(engine):
    app = create_service_app("procurement-service", validator=Roles())
    assert TestClient(app).post("/internal/suppliers/import", json={"rows": []}, headers=h()).status_code == 404


def test_it_needs_the_loader_identity(client):
    assert client.post("/internal/suppliers/import", json={"rows": []}).status_code == 401
    assert post(client, [], "viewer").status_code == 403
    assert post(client, [], "loader").status_code == 200


def test_new_suppliers_are_imported_unverified_with_their_erp_reference(client, engine):
    r = post(client, [row(), row(9100002, "Proveedor Sintetico Dos", payment_terms_days=None, has_note=True, currency="USD", fiscal_type="foreign", country="US")])
    assert r.json() == {"created": 2, "existing": 0, "possible_duplicates": 0, "unparsed_terms": 0, "suggested_non_purchasing": 0}
    with engine.connect() as c:
        got = {s.external_contact_id: s for s in c.execute(select(suppliers)).all()}
    one, two = got[9100001], got[9100002]
    assert (one.origin, one.erp_link_state, one.classification, one.status, one.payment_terms_days) == ("imported", "unverified", "unclassified", "active", 30)
    assert (two.currency, two.fiscal_type, two.country, two.has_note, two.payment_terms_days) == ("USD", "foreign", "US", True, None)
    assert one.created_by == "svc-loader"


def test_reimporting_is_idempotent_and_never_overwrites_buyer_edits(client, engine):
    post(client, [row()])
    with engine.begin() as c:
        c.execute(suppliers.update().where(suppliers.c.external_contact_id == 9100001).values(name="Nombre editado", classification="purchasing", currency="EUR"))
    again = post(client, [row(name="Otro nombre del archivo", payment_terms_days=45)])
    assert again.json()["created"] == 0 and again.json()["existing"] == 1
    with engine.connect() as c:
        s = c.execute(select(suppliers)).one()
    assert (s.name, s.classification, s.payment_terms_days) == ("Nombre editado", "purchasing", 30)


def test_missing_payment_terms_are_filled_later_but_never_replaced(client, engine):
    post(client, [row(payment_terms_days=None)])
    post(client, [row(payment_terms_days=15)])
    with engine.connect() as c:
        assert c.execute(select(suppliers.c.payment_terms_days)).scalar() == 15


def test_an_erp_supplier_with_the_same_contact_id_is_left_alone(client, engine):
    with engine.begin() as c:
        add_supplier(c, 9100001, "Nombre del ERP")
    r = post(client, [row()])
    assert r.json()["existing"] == 1 and r.json()["created"] == 0
    with engine.connect() as c:
        assert c.execute(select(suppliers.c.name)).scalar() == "Nombre del ERP"


def test_lookalike_names_are_both_created_and_flagged_for_review_without_names(client, engine):
    r = post(client, [row(1, "Distribuciones Sinteticas Norte S.L."), row(2, "DISTRIBUCIONES SINTÉTICAS NORTE SL")])
    assert r.json()["created"] == 2 and r.json()["possible_duplicates"] == 1
    with engine.connect() as c:
        items = c.execute(select(supplier_review_items)).all()
    assert [i.kind for i in items] == ["possible_duplicate"] and "Distribuciones" not in items[0].detail


def test_unparsed_payment_terms_are_listed_once(client, engine):
    post(client, [row(terms_unparsed=True, payment_terms_days=None)])
    r = post(client, [row(terms_unparsed=True, payment_terms_days=None)])
    assert r.json()["unparsed_terms"] == 0
    with engine.connect() as c:
        assert [i.kind for i in c.execute(select(supplier_review_items)).all()] == ["payment_terms_unparsed"]


def test_obvious_expense_vendors_are_suggested_as_non_purchasing(client, engine):
    r = post(client, [row(1, "Energia Sintetica S.A."), row(2, "Distribuciones Veterinarias Sinteticas")])
    assert r.json()["suggested_non_purchasing"] == 1
    with engine.connect() as c:
        got = {s.external_contact_id: s.classification for s in c.execute(select(suppliers)).all()}
    assert got == {1: "non_purchasing", 2: "unclassified"}


@pytest.mark.parametrize(("name", "expected"), [
    ("Energia Sintetica S.A.", "non_purchasing"), ("SEGUROS SINTÉTICOS", "non_purchasing"), ("Telecom Sintetica", "non_purchasing"), ("Hosting Sintetico Ltd", "non_purchasing"),
    ("Software y Servicios Sinteticos", "non_purchasing"), ("Alarmas Sinteticas", "non_purchasing"), ("Asesoria Sintetica", "non_purchasing"),
    ("Distribuciones Veterinarias Sinteticas", "unclassified"), ("Alimentos para Mascotas Sinteticos", "unclassified"), ("Seguro Sanitario Mascotas Distribuciones", "non_purchasing"),
    ("Gasolineras", "unclassified"),
])
def test_the_suggestion_rule(name, expected):
    assert suggest_classification(name) == expected


@pytest.mark.parametrize("bad", [
    {**row(), "cif": "X1"}, {**row(), "notes": "libre"}, {**row(), "iban": "ES00"}, row(0), row(-1), row(name=""), row(name="x" * 201), row(country="ESP"), row(currency="euro"),
    row(fiscal_type="otro"), row(payment_terms_days=400), row(payment_terms_days=1.5),
])
def test_invalid_or_sensitive_rows_are_refused(client, bad):
    assert post(client, [bad]).status_code == 422


def test_too_many_rows_are_refused(client):
    assert post(client, [row(i + 1, f"P{i}") for i in range(5001)]).status_code == 422
