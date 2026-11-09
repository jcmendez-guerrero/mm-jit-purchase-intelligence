"""T050: the supplier endpoints: roles, stable codes, If-Match, previews, links, bulk assignment, merge. Synthetic data only."""

from decimal import Decimal

import pytest
from api import costs
from api.suppliers import build_router
from conftest import NOW
from db.tables import export_costs
from fastapi.testclient import TestClient
from mmi_common.auth import AuthError, Principal
from mmi_common.service import create_service_app
from sqlalchemy import insert
from suppliers_support import make_ref, open_line

ROLES = {"viewer": {"viewer"}, "buyer": {"viewer", "buyer"}, "admin": {"viewer", "admin"}}


class Validator:
    def validate(self, token, required_roles=()):
        roles = ROLES.get(token, set())
        if not set(required_roles) <= roles:
            raise AuthError("forbidden", 403)
        return Principal(subject=f"user-{token}", roles=frozenset(roles), auth_time=None)


def h(role="buyer", **extra):
    return {"Authorization": f"Bearer {role}", **extra}


BODY = {"name": "Proveedor Sintetico Uno", "fiscal_type": "national", "country": "ES", "currency": "EUR"}


@pytest.fixture
def client(engine):
    app = create_service_app("procurement-service", validator=Validator())
    app.include_router(costs.build_router(app))
    app.include_router(build_router(app))
    app.dependency_overrides[costs.get_engine] = lambda: engine
    return TestClient(app)


def create(client, role="buyer", **kw):
    r = client.post("/suppliers", json={**BODY, **kw}, headers=h(role))
    assert r.status_code == 201, r.text
    return r.json()


def test_reads_need_a_session_and_writes_need_buyer_or_admin(client):
    assert client.get("/suppliers").status_code == 401
    assert client.post("/suppliers", json=BODY, headers=h("viewer")).status_code == 403
    assert client.post("/suppliers", json=BODY, headers=h("buyer")).status_code == 201
    assert client.post("/suppliers", json={**BODY, "name": "Otro"}, headers=h("admin")).status_code == 201
    assert client.get("/suppliers", headers=h("viewer")).status_code == 200


def test_unknown_fields_such_as_tax_id_or_notes_are_refused(client):
    for extra in ({"cif": "X1"}, {"iban": "ES00"}, {"notes": "libre"}, {"tax_id": "1"}):
        assert client.post("/suppliers", json={**BODY, **extra}, headers=h()).status_code == 422


def test_create_returns_the_supplier_and_a_duplicate_needs_confirmation(client):
    first = create(client)
    assert (first["origin"], first["status"], first["erp_link_state"], first["version"]) == ("platform", "active", "none", 1)
    dup = client.post("/suppliers", json={**BODY, "name": "PROVEEDOR SINTÉTICO UNO"}, headers=h())
    assert dup.status_code == 409 and dup.json()["detail"] == "supplier_possible_duplicate" and dup.json()["duplicates"] == [first["id"]]
    assert client.post("/suppliers?confirm_duplicate=true", json={**BODY, "name": "PROVEEDOR SINTÉTICO UNO"}, headers=h()).status_code == 201
    assert len(client.get("/suppliers/review-items", headers=h()).json()) == 1


def test_validation_errors_name_the_field(client):
    r = client.post("/suppliers", json={**BODY, "country": "ESP"}, headers=h())
    assert r.status_code == 422 and r.json() == {"detail": "supplier_invalid", "field": "country"}


def test_patch_needs_if_match_and_reports_the_current_version_on_conflict(client):
    s = create(client)
    assert client.patch(f"/suppliers/{s['id']}", json={"payment_terms_days": 30}, headers=h()).status_code == 428
    ok = client.patch(f"/suppliers/{s['id']}", json={"payment_terms_days": 30}, headers=h(**{"If-Match": '"1"'}))
    assert ok.status_code == 200 and ok.json()["version"] == 2 and ok.json()["payment_terms_days"] == 30
    stale = client.patch(f"/suppliers/{s['id']}", json={"payment_terms_days": 45}, headers=h(**{"If-Match": '"1"'}))
    assert stale.status_code == 412 and stale.json() == {"detail": "supplier_version_conflict", "current_version": 2}


def test_unknown_supplier_is_a_404_with_a_stable_code(client):
    assert client.get("/suppliers/nope", headers=h()).json() == {"detail": "supplier_not_found"}


def test_deactivation_previews_then_confirms_and_reactivation_restores(client, engine):
    s = create(client)
    with engine.begin() as c:
        open_line(c, s["id"], 1, "draft")
    prev = client.post(f"/suppliers/{s['id']}/deactivate", json={"confirm": False}, headers=h()).json()
    assert prev["deactivated"] is False and prev["open_proposal_lines"] == 1
    done = client.post(f"/suppliers/{s['id']}/deactivate", json={"confirm": True}, headers=h("admin")).json()
    assert done["deactivated"] is True
    assert client.get(f"/suppliers/{s['id']}", headers=h()).json()["status"] == "deactivated"
    assert client.post(f"/suppliers/{s['id']}/reactivate", headers=h()).json()["status"] == "active"


def test_the_list_filters_and_keeps_the_terms_fields(client):
    a = create(client, name="Alfa Sintetica")
    create(client, name="Beta Sintetica", classification="non_purchasing")
    names = lambda qs: [s["name"] for s in client.get(f"/suppliers{qs}", headers=h()).json()]  # noqa: E731
    assert names("") == ["Alfa Sintetica", "Beta Sintetica"] and names("?classification=non_purchasing") == ["Beta Sintetica"] and names("?q=alf") == ["Alfa Sintetica"]
    row = client.get("/suppliers", headers=h()).json()[0]
    assert row["id"] == a["id"] and {"terms", "version", "supplier_version", "erp_link_state"} <= set(row)


def test_links_by_sku(client, engine):
    with engine.begin() as c:
        make_ref(c, 1, 10, "SYN-000001", name="Pienso")
    s = create(client)
    put = client.put(f"/suppliers/{s['id']}/links/SYN-000001", json={"cost": "100.00", "includes_recargo": False, "pack_size": 6}, headers=h())
    assert put.status_code == 200 and put.json()["cost"] == "105.2000" and put.json()["write_case"] == "pending_link"
    listed = client.get(f"/suppliers/{s['id']}/links", headers=h()).json()
    assert [(x["sku"], x["cost"], x["pack_size"]) for x in listed] == [("SYN-000001", "105.2000", 6)]
    assert client.put(f"/suppliers/{s['id']}/links/SYN-404", json={"cost": "1"}, headers=h()).json() == {"detail": "link_sku_unknown", "field": "sku"}
    assert client.put(f"/suppliers/{s['id']}/links/SYN-000001", json={"cost": "1", "bogus": 1}, headers=h()).status_code == 422
    assert client.delete(f"/suppliers/{s['id']}/links/SYN-000001", headers=h()).status_code == 204
    assert client.get(f"/suppliers/{s['id']}/links", headers=h()).json() == []
    assert client.delete(f"/suppliers/{s['id']}/links/SYN-000001", headers=h()).json() == {"detail": "link_not_found"}


def test_bulk_preview_apply_and_stale_codes(client, engine):
    with engine.begin() as c:
        for i in (1, 2, 3):
            make_ref(c, i, 100 + i, f"SYN-{i:06d}", name=f"Producto {i}")
            c.execute(insert(export_costs).values(sku=f"SYN-{i:06d}", export_cost=Decimal("2.00"), pvp_gross=Decimal("4"), tax_rate=Decimal("21"), tax_included=False, currency="EUR", loaded_at=NOW))
    s = create(client)
    assert client.post(f"/suppliers/{s['id']}/links/bulk/preview", json={}, headers=h()).json() == {"detail": "bulk_criteria_invalid"}
    p = client.post(f"/suppliers/{s['id']}/links/bulk/preview", json={"q": "producto"}, headers=h()).json()
    assert (p["matched"], p["new"]) == (3, 3)
    out = client.post(f"/suppliers/{s['id']}/links/bulk/apply", json={"batch_id": p["batch_id"]}, headers=h())
    assert out.json() == {"changed": 3, "skipped_conflicts": 0, "no_cost": 0, "rows": [{"sku": f"SYN-{i:06d}", "outcome": "linked"} for i in (1, 2, 3)]}
    assert client.post(f"/suppliers/{s['id']}/links/bulk/apply", json={"batch_id": p["batch_id"]}, headers=h()).json() == {"detail": "bulk_preview_stale"}
    assert len(client.get(f"/suppliers/{s['id']}/links", headers=h()).json()) == 3


def test_assignment_file_is_parsed_into_groups(client):
    s = create(client, name="Proveedor Alfa")
    r = client.post("/links/bulk/file", files={"file": ("a.csv", b"SKU;Proveedor\nSYN-000001;proveedor alfa\nSYN-000002;Nadie\n", "text/csv")}, headers=h())
    assert r.json()["groups"] == {s["id"]: ["SYN-000001"]} and r.json()["errors"] == [{"row": 3, "code": "link_no_match"}]
    assert client.post("/links/bulk/file", files={"file": ("a.xlsm", b"x", "x/y")}, headers=h()).status_code == 415
    assert client.post("/links/bulk/file", files={"file": ("a.csv", b"x" * (5 * 1024 * 1024 + 1), "text/csv")}, headers=h()).status_code == 413
    assert client.post("/links/bulk/file", files={"file": ("a.csv", b"a,b\n1,2\n", "text/csv")}, headers=h()).json() == {"detail": "bulk_file_invalid"}


def test_merge_and_review_resolution(client):
    a = create(client, name="Proveedor Alfa")
    b = client.post("/suppliers?confirm_duplicate=true", json={**BODY, "name": "PROVEEDOR ALFA"}, headers=h()).json()
    item = client.get("/suppliers/review-items", headers=h()).json()[0]
    assert client.post(f"/suppliers/review-items/{item['id']}/resolve", json={"decision": "maybe"}, headers=h()).status_code == 422
    assert client.post(f"/suppliers/review-items/{item['id']}/resolve", json={"decision": "merge_into", "merge_into": a["id"]}, headers=h("viewer")).status_code == 403
    assert client.post(f"/suppliers/review-items/{item['id']}/resolve", json={"decision": "merge_into", "merge_into": a["id"]}, headers=h()).status_code == 204
    assert client.get(f"/suppliers/{b['id']}", headers=h()).json()["merged_into"] == a["id"]
    assert client.post(f"/suppliers/{a['id']}/merge", json={"merge_into": a["id"]}, headers=h()).json() == {"detail": "merge_same_supplier"}
