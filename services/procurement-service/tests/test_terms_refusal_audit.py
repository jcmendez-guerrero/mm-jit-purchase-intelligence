# ruff: noqa: F811
"""T042 (FR-026, FR-028, SC-007): every refused change request leaves a tamper-evident audit entry with who, what it targeted, the stable error code
and the HTTP status, and never the request body. Recording can never change the answer the caller gets.
"""

from __future__ import annotations

import json

from audit.chain import verify_chain
from conftest import add_product
from db.tables import audit_events
from refusal_support import app, client, engine, h, refusals, sid  # noqa: F401
from sqlalchemy import select
from test_terms_api import BODY

FREE_TEXT = "TEXTO-LIBRE-QUE-NO-DEBE-QUEDAR-EN-LA-AUDITORIA"


def test_a_stale_if_match_is_recorded_as_a_412_with_the_actor_and_the_target(client, engine, sid):
    client.put(f"/suppliers/{sid}/terms", json=BODY, headers=h())
    client.put(f"/suppliers/{sid}/terms", json={**BODY, "lead_time_days": 4}, headers=h(**{"If-Match": '"1"'}))
    stale = client.put(f"/suppliers/{sid}/terms", json={**BODY, "lead_time_days": 9}, headers=h(**{"If-Match": '"1"'}))
    assert stale.status_code == 412
    assert refusals(engine) == [("user-buyer", "terms.refused", "supplier_terms", sid, {"code": "revision_conflict", "status": 412}, None)]


def test_a_missing_if_match_is_recorded_as_a_428(client, engine, sid):
    client.put(f"/suppliers/{sid}/terms", json=BODY, headers=h())
    assert client.put(f"/suppliers/{sid}/terms", json=BODY, headers=h()).status_code == 428
    assert [(r[1], r[4]) for r in refusals(engine)] == [("terms.refused", {"code": "revision_required", "status": 428})]


def test_invalid_terms_are_recorded_as_a_422_with_their_specific_code(client, engine, sid):
    assert client.put(f"/suppliers/{sid}/terms", json={**BODY, "delivery_charge": "-1"}, headers=h()).status_code == 422
    assert [r[4] for r in refusals(engine)] == [{"code": "terms_negative_amount", "status": 422}]


def test_a_body_the_schema_rejects_is_recorded_as_request_invalid(client, engine, sid):
    assert client.put(f"/suppliers/{sid}/terms", json={**BODY, "min_order_value": "abc"}, headers=h()).status_code == 422
    assert [r[4] for r in refusals(engine)] == [{"code": "request_invalid", "status": 422}]


def test_a_viewer_is_recorded_as_a_403_with_the_catalogue_code(client, engine, sid):
    refused = client.put(f"/suppliers/{sid}/terms", json=BODY, headers=h("viewer"))
    assert refused.status_code == 403 and refused.json() == {"detail": "auth_forbidden_role"}
    assert refusals(engine) == [("user-viewer", "terms.refused", "supplier_terms", sid, {"code": "auth_forbidden_role", "status": 403}, None)]


def test_an_anonymous_caller_is_refused_with_a_401_and_not_stored_one_by_one(client, engine, sid):
    """FR-038: no valid sign-in is counted, not stored (the volume tests are in test_refusal_volume.py)."""
    assert client.put(f"/suppliers/{sid}/terms", json=BODY).status_code == 401
    assert refusals(engine) == []


def test_product_override_refusals_name_the_pair_by_sku(client, engine, sid):
    with engine.begin() as c:
        add_product(c, 1, 10, sku="SYN-0001")
    client.put(f"/product-suppliers/SYN-0001/{sid}/terms", json={"lead_time_days": 5}, headers=h())
    assert client.put(f"/product-suppliers/SYN-0001/{sid}/terms", json={"lead_time_days": 6}, headers=h()).status_code == 428
    assert [(r[1], r[2], r[3]) for r in refusals(engine)] == [("terms.refused", "product_supplier_terms", f"SYN-0001:{sid}")]


def test_an_unknown_sku_is_recorded_as_a_422_with_the_sku_and_no_variant_id(client, engine, sid):
    assert client.put(f"/product-suppliers/SYN-NO-EXISTE/{sid}/terms", json={"lead_time_days": 5}, headers=h()).status_code == 422
    assert [(r[1], r[2], r[3], r[4]) for r in refusals(engine)] == [
        ("terms.refused", "product_supplier_terms", f"SYN-NO-EXISTE:{sid}", {"code": "sku_unknown", "status": 422})]


def test_a_long_sku_is_cut_in_the_refusal_entry_not_the_supplier_id(client, engine, sid):
    long_sku = "SYN-NO-EXISTE-" + "L" * 30
    assert client.put(f"/product-suppliers/{long_sku}/{sid}/terms", json={"lead_time_days": 5}, headers=h()).status_code == 422
    (entry,) = [r[3] for r in refusals(engine)]
    assert len(entry) == 60 and entry.endswith(f":{sid}") and entry.startswith("SYN-NO-EXISTE")


def test_supplier_and_link_refusals_use_their_own_actions(client, engine, sid):
    duplicate = {"name": "Proveedor Sintetico", "fiscal_type": "national", "country": "ES", "currency": "EUR"}
    assert client.post("/suppliers", json=duplicate, headers=h()).status_code == 409
    assert client.put(f"/suppliers/{sid}/links/SYN-NO-EXISTE", json={"cost": "1.00"}, headers=h()).status_code == 422
    assert [(r[1], r[2], r[4]["code"]) for r in refusals(engine)] == [
        ("supplier.refused", "supplier", "supplier_possible_duplicate"), ("link.refused", "supplier_link", "link_sku_unknown")]


def test_a_request_body_never_reaches_the_audit_trail(client, engine, sid):
    client.put(f"/suppliers/{sid}/terms", json={**BODY, "delivery_charge": "-1", "reason": FREE_TEXT}, headers=h())
    client.post("/suppliers", json={"name": FREE_TEXT, "fiscal_type": "national", "country": "ES", "currency": "EURO"}, headers=h())
    with engine.begin() as c:
        everything = json.dumps([[str(v) for v in r] for r in c.execute(select(audit_events)).all()])
    assert refusals(engine) and FREE_TEXT not in everything


def test_successful_changes_and_reads_record_no_refusal(client, engine, sid):
    assert client.put(f"/suppliers/{sid}/terms", json=BODY, headers=h()).status_code == 200
    assert client.get(f"/suppliers/{sid}/terms", headers=h("viewer")).status_code == 200
    assert client.get("/suppliers/does-not-exist", headers=h("viewer")).status_code == 404         # a read of something missing is not a refused change
    assert refusals(engine) == []


def test_the_chain_still_verifies_after_refusals_and_keeps_every_link(client, engine, sid):
    for charge in ("-1", "-2", "-3"):                              # three different values would still be one reason, so use three targets
        client.put(f"/suppliers/{sid}-{charge}/terms", json={**BODY, "delivery_charge": charge}, headers=h())
    with engine.begin() as c:
        check = verify_chain(c)
    assert check.ok and len(refusals(engine)) == 3


def test_a_failure_to_record_never_changes_the_answer(client, engine, sid, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("audit store down")

    monkeypatch.setattr("api.refusals.record_refusal", broken)
    refused = client.put(f"/suppliers/{sid}/terms", json={**BODY, "delivery_charge": "-1"}, headers=h())
    assert refused.status_code == 422 and refused.json() == {"detail": "terms_negative_amount"}
