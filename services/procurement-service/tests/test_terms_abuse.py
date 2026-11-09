# ruff: noqa: F811
"""T043 (FR-028, SC-007): abusive input is refused with a stable catalogue code, never a server error, stores nothing, and is recorded.

Covers oversized bodies, malformed and non-finite numbers, values too large for the database, out-of-range values, too many items, replayed keys
with other content, and probing another supplier's links or a SKU written as an injection.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import NOW
from db.tables import audit_events, supplier_terms, suppliers
from sqlalchemy import func, select
from suppliers.service import SupplierInput, create_supplier
from terms.service import history
from test_terms_api import BODY
from test_terms_refusal_audit import app, client, engine, h, refusals  # noqa: F401  (fixtures: a file database so refusals can be recorded beside the request)

CATALOGUE = set(json.loads((Path(__file__).resolve().parents[3] / "packages" / "contracts" / "errors" / "error_codes.json").read_text(encoding="utf-8"))["codes"])


@pytest.fixture
def sid(engine):
    with engine.begin() as c:
        return create_supplier(c, SupplierInput(name="Proveedor Sintetico", fiscal_type="national", country="ES", currency="EUR"), "buyer-1", now=NOW).id


def versions(engine, sid):
    with engine.begin() as c:
        return len(history(c, sid))


def code_of(res):
    """The stable code of a refusal: the schema's own rejections come back as a list, which is the one code request_invalid."""
    detail = res.json()["detail"]
    return detail if isinstance(detail, str) else "request_invalid"


def put(client, sid, patch, **headers):
    return client.put(f"/suppliers/{sid}/terms", json={**BODY, **patch}, headers=h(**headers))


@pytest.mark.parametrize(("label", "patch", "status", "code"), [
    ("negative money", {"delivery_charge": "-1"}, 422, "terms_negative_amount"),
    ("not a number", {"min_order_value": "abc"}, 422, "request_invalid"),
    ("not a number (empty)", {"min_order_value": ""}, 422, "request_invalid"),
    ("NaN", {"min_order_value": "NaN"}, 422, "request_invalid"),
    ("infinity", {"min_order_value": "Infinity"}, 422, "request_invalid"),
    ("minus infinity", {"delivery_charge": "-Infinity"}, 422, "request_invalid"),
    ("too large for the column", {"min_order_value": "1e30", "free_delivery_threshold": "1e31"}, 422, "terms_invalid_value"),
    ("absurd quantity", {"min_qty_for_delivery": 10**30}, 422, "terms_invalid_value"),
    ("lead time out of range", {"lead_time_days": 999}, 422, "terms_invalid_value"),
    ("weekday out of range", {"order_days": [9]}, 422, "terms_invalid_weekday"),
    ("percentage above 100", {"discounts": [{"kind": "percent", "basis": "order_value", "threshold": "10", "value": "150"}]}, 422, "terms_invalid_value"),
    ("non-finite discount", {"discounts": [{"kind": "percent", "basis": "order_value", "threshold": "10", "value": "NaN"}]}, 422, "request_invalid"),
    ("bad cutoff time", {"order_cutoff_time": "25:99"}, 422, "terms_invalid_value"),
    ("too many weekdays", {"order_days": list(range(1, 10))}, 422, "request_invalid"),
    ("too many discount tiers", {"discounts": [{"kind": "percent", "basis": "order_value", "threshold": "10", "value": "1"}] * 11}, 422, "request_invalid"),
    ("reason too long", {"reason": "x" * 501}, 422, "request_invalid"),
    ("window ends before it starts", {"valid_from": "2030-01-02T00:00:00Z", "valid_to": "2030-01-01T00:00:00Z"}, 422, "terms_window_overlap"),
])
def test_abusive_terms_are_refused_with_a_catalogue_code_store_nothing_and_are_recorded(client, engine, sid, label, patch, status, code):
    res = put(client, sid, patch)
    assert (res.status_code, code_of(res)) == (status, code), label
    assert code in CATALOGUE and versions(engine, sid) == 0
    assert [r[4] for r in refusals(engine)] == [{"code": code, "status": status}]


def test_an_oversized_body_is_refused_before_it_is_read_into_the_terms(client, engine, sid):
    res = put(client, sid, {"reason": "x" * 300_000})
    assert (res.status_code, res.json()) == (413, {"detail": "payload_too_large"})
    assert "payload_too_large" in CATALOGUE and versions(engine, sid) == 0
    assert [r[4] for r in refusals(engine)] == [{"code": "payload_too_large", "status": 413}]


def test_a_replayed_key_with_other_content_is_refused_and_recorded(client, engine, sid):
    assert put(client, sid, {}, **{"Idempotency-Key": "k-1"}).status_code == 200
    replay = put(client, sid, {"lead_time_days": 9}, **{"Idempotency-Key": "k-1"})
    assert (replay.status_code, replay.json()) == (422, {"detail": "idempotency_key_reuse"}) and versions(engine, sid) == 1
    assert [r[4] for r in refusals(engine)] == [{"code": "idempotency_key_reuse", "status": 422}]


def test_a_terms_save_for_a_supplier_that_does_not_exist_is_refused(client, engine, sid):
    res = client.put("/suppliers/00000000-0000-0000-0000-000000000000/terms", json=BODY, headers=h())
    assert res.status_code in (404, 422) and code_of(res) in CATALOGUE
    with engine.begin() as c:
        assert c.execute(select(func.count()).select_from(supplier_terms)).scalar() == 0


def test_another_suppliers_link_cannot_be_removed_through_this_one(client, engine, sid):
    from conftest import NOW as now
    from costs.recargo import load_table
    from costs.rules import CostRules
    from suppliers.links import LinkInput, put_link
    from suppliers_support import make_ref

    with engine.begin() as c:
        make_ref(c, 1, 10, "SYN-000001")
        other = create_supplier(c, SupplierInput(name="Otro Proveedor", fiscal_type="national", country="ES", currency="EUR"), "buyer-1", now=now).id
        put_link(c, other, "SYN-000001", LinkInput(cost=__import__("decimal").Decimal("2.00"), includes_recargo=True), "buyer-1", CostRules(), load_table(c), now=now)
    res = client.delete(f"/suppliers/{sid}/links/SYN-000001", headers=h())
    assert (res.status_code, res.json()) == (404, {"detail": "link_not_found"})
    listed = client.get(f"/suppliers/{other}/links", headers=h("viewer")).json()
    assert [row["sku"] for row in listed] == ["SYN-000001"]                                       # the other supplier's link is intact
    assert [(r[1], r[4]) for r in refusals(engine)] == [("link.refused", {"code": "link_not_found", "status": 404})]


@pytest.mark.parametrize("sku", ["SYN-1'; DROP TABLE suppliers;--", "..%2F..%2Fetc%2Fpasswd", "%00", "A" * 5000])
def test_a_hostile_sku_is_an_unknown_sku_never_an_error_or_an_injection(client, engine, sid, sku):
    res = client.put(f"/suppliers/{sid}/links/{sku}", json={"cost": "1.00"}, headers=h())
    assert res.status_code < 500 and code_of(res) in CATALOGUE
    with engine.begin() as c:
        assert c.execute(select(func.count()).select_from(suppliers)).scalar() == 1             # the table is still there with its row


def test_no_abuse_case_above_ever_reaches_a_server_error_in_the_audit_either(client, engine, sid):
    put(client, sid, {"min_order_value": "NaN"})
    with engine.begin() as c:
        statuses = [r.after["status"] for r in c.execute(select(audit_events)).all() if r.action.endswith(".refused")]
    assert statuses and all(400 <= s < 500 for s in statuses)
