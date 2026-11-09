"""T053: terms endpoints - history, If-Match concurrency, roles, validation codes, product overrides and the effective view."""

from datetime import UTC, datetime
from decimal import Decimal

from conftest import add_product, add_supplier, auth
from costs.rules import CostRules
from costs.store import NewCost, add_version
from db.tables import product_refs  # noqa: F401  (the variant -> product map used to find the ERP cost behind a pair)

BODY = {"min_order_value": "150.00", "free_delivery_threshold": "300", "delivery_charge": "9.5", "order_days": [1, 4], "lead_time_days": 3,
        "delivery_weekdays": [2, 5], "order_cutoff_time": "13:30", "payment_terms_days": 30, "preferred": True,
        "discounts": [{"kind": "percent", "basis": "order_value", "threshold": "500", "value": "3"}], "reason": "alta inicial"}


def seed(engine):
    with engine.begin() as c:
        sid = add_supplier(c, 1, "Proveedor Sintético A")
        add_product(c, 9001, 10)
    return sid


def put(client, sid, body=BODY, etag=None, role="buyer"):
    headers = auth(role)
    if etag is not None:
        headers["If-Match"] = f'"{etag}"'
    return client.put(f"/suppliers/{sid}/terms", json=body, headers=headers)


def test_the_first_save_needs_no_precondition_but_later_ones_do(client, engine):
    sid = seed(engine)
    assert put(client, sid).json() == {"version": 1}
    r = put(client, sid, {**BODY, "lead_time_days": 4})
    assert r.status_code == 428 and r.json() == {"detail": "revision_required"}
    assert put(client, sid, {**BODY, "lead_time_days": 4}, etag=1).json() == {"version": 2}


def test_a_stale_precondition_is_a_412_that_names_the_current_version(client, engine):
    sid = seed(engine)
    put(client, sid)
    put(client, sid, {**BODY, "lead_time_days": 4}, etag=1)
    r = put(client, sid, {**BODY, "lead_time_days": 9}, etag=1)                     # based on the version it read before the other edit
    assert r.status_code == 412 and r.json() == {"detail": "revision_conflict", "current_version": 2}
    assert client.get(f"/suppliers/{sid}/terms", headers=auth()).json()["current"]["lead_time_days"] == 4


def test_a_garbled_precondition_is_a_validation_error(client, engine):
    sid = seed(engine)
    put(client, sid)
    r = client.put(f"/suppliers/{sid}/terms", json=BODY, headers={**auth("buyer"), "If-Match": "not-a-number"})
    assert r.status_code == 400 and r.json() == {"detail": "request_invalid"}


def test_reading_returns_the_current_terms_the_version_to_send_back_and_the_history(client, engine):
    sid = seed(engine)
    put(client, sid)
    put(client, sid, {**BODY, "lead_time_days": 4, "reason": "nuevo transportista"}, etag=1)
    body = client.get(f"/suppliers/{sid}/terms", headers=auth("viewer")).json()
    assert body["version"] == 2 and body["current"]["lead_time_days"] == 4 and body["current"]["discounts"][0]["value"] == "3"
    assert [(h["version"], h["reason"], h["changed_by"]) for h in body["history"]] == [(1, "alta inicial", "user-buyer"), (2, "nuevo transportista", "user-buyer")]
    assert client.get(f"/suppliers/{sid}/terms?as_of=2020-01-01T00:00:00Z", headers=auth()).json()["current"] is None


def test_each_history_item_says_whether_it_is_in_force_planned_superseded_or_expired(client, engine):
    sid = seed(engine)
    put(client, sid)
    put(client, sid, {**BODY, "lead_time_days": 4}, etag=1)
    put(client, sid, {**BODY, "lead_time_days": 9, "valid_from": "2099-01-01T00:00:00Z"}, etag=2)
    status = {h["version"]: h["status"] for h in client.get(f"/suppliers/{sid}/terms", headers=auth()).json()["history"]}
    assert status == {1: "superseded", 2: "in_force", 3: "planned"}
    far = client.get(f"/suppliers/{sid}/terms?as_of=2100-01-01T00:00:00Z", headers=auth()).json()["history"]
    assert {h["version"]: h["status"] for h in far} == {1: "superseded", 2: "superseded", 3: "in_force"}


def test_roles_are_enforced(client, engine):
    sid = seed(engine)
    assert put(client, sid, role="viewer").status_code == 403
    assert client.put(f"/suppliers/{sid}/terms", json=BODY).status_code == 401
    assert client.get(f"/suppliers/{sid}/terms").status_code == 401


def test_invalid_terms_come_back_as_specific_codes_and_store_nothing(client, engine):
    sid = seed(engine)
    cases = {"terms_negative_amount": {"delivery_charge": "-1"}, "terms_threshold_below_minimum": {"min_order_value": "400"},
             "terms_invalid_weekday": {"order_days": [0]}, "terms_invalid_value": {"lead_time_days": 999}, "terms_window_overlap": {"valid_to": "2000-01-01T00:00:00Z"}}
    for code, patch in cases.items():
        r = put(client, sid, {**BODY, **patch})
        assert r.status_code == 422 and r.json() == {"detail": code}, (code, r.text)
    assert client.get(f"/suppliers/{sid}/terms", headers=auth()).json()["version"] == 0


def test_the_supplier_list_shows_the_new_fields_for_the_editor(client, engine):
    sid = seed(engine)
    put(client, sid)
    t = client.get("/suppliers", headers=auth()).json()[0]["terms"]
    assert t["lead_time_days"] == 3 and t["preferred"] is True and t["disabled"] is False and t["delivery_weekdays"] == [2, 5]


def test_a_product_override_and_the_effective_view(client, engine):
    sid = seed(engine)
    put(client, sid)
    url = f"/product-suppliers/9001/{sid}/terms"
    assert client.get(url, headers=auth()).json()["override"] is None
    r = client.put(url, json={"lead_time_days": 5, "pack_multiple": 12, "reason": "caja de 12"}, headers=auth("buyer"))
    assert r.status_code == 200 and r.json() == {"version": 1}
    view = client.get(url, headers=auth()).json()
    assert view["override"]["pack_multiple"] == 12 and view["version"] == 1
    assert view["effective"]["lead_time_days"] == 5 and view["effective"]["sources"]["lead_time_days"] == "override"
    assert view["effective"]["sources"]["preferred"] == "supplier"
    assert client.put(url, json={"lead_time_days": 6}, headers=auth("buyer")).status_code == 428
    stale = client.put(url, json={"lead_time_days": 6}, headers={**auth("buyer"), "If-Match": '"0"'})
    assert stale.status_code == 412 and stale.json()["current_version"] == 1
    assert client.put(url, json={"pack_multiple": 0}, headers={**auth("buyer"), "If-Match": '"1"'}).json() == {"detail": "terms_invalid_value"}
    assert client.put(url, json={"lead_time_days": 6}, headers=auth("viewer")).status_code == 403


def test_the_effective_view_reports_conflicts_with_an_erp_value(client, engine):
    sid = seed(engine)
    with engine.begin() as c:
        add_version(c, NewCost(product_id=10, supplier_id=sid, cost_with_recargo=Decimal("1.00"), source="siweb_product_supplier", actor="siweb-import",
                               pack_size=6, lead_time_days=4), CostRules(), datetime.now(UTC))
    client.put(f"/product-suppliers/9001/{sid}/terms", json={"pack_multiple": 12}, headers=auth("buyer"))
    eff = client.get(f"/product-suppliers/9001/{sid}/terms", headers=auth()).json()["effective"]
    assert eff["pack_multiple"] == 12 and {"field": "pack_multiple", "erp_value": 6, "local_value": 12, "winner": "local"} in eff["conflicts"]
