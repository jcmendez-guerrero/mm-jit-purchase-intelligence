"""T082: cost, terms and price-list endpoints."""

import io
from datetime import UTC, datetime
from decimal import Decimal

from conftest import add_product, add_supplier, auth
from db.tables import erp_supplier_links
from sqlalchemy import insert


def test_reads_need_authentication_and_writes_need_the_buyer_role(client, engine):
    assert client.get("/costs").status_code == 401
    assert client.post("/costs", json={}, headers=auth("viewer")).status_code == 403
    assert client.put("/suppliers/x/terms", json={}, headers=auth("viewer")).status_code == 403
    assert client.post("/costs/c/verify", headers=auth("viewer")).status_code == 403


def seed(engine, vat=Decimal("21")):
    with engine.begin() as c:
        sid = add_supplier(c)
        add_product(c, 10, 1, vat=vat)
    return sid


def test_net_entry_shows_the_cost_with_recargo_and_flags_the_write_case(client, engine):
    sid = seed(engine)
    with engine.begin() as c:
        c.execute(insert(erp_supplier_links).values(product_id=1, supplier_id=sid, has_cost=False, last_seen_at=datetime.now(UTC)))
    r = client.post("/costs", json={"product_id": 1, "supplier_id": sid, "amount": "100.00", "includes_recargo": False}, headers=auth("buyer"))
    assert r.status_code == 201
    body = r.json()
    assert body["cost"]["cost_with_recargo"] == "105.2000" and body["cost"]["cost_net"] == "100.0000" and body["cost"]["source"] == "manual"
    assert body["erp_link"] == "link_without_cost" and body["write_case"] == "missing_cost" and body["cost"]["status"] == "ok"


def test_entry_without_an_erp_link_keeps_the_cost_locally_and_marks_pending_link(client, engine):
    sid = seed(engine)
    r = client.post("/costs", json={"product_id": 1, "supplier_id": sid, "amount": "10", "includes_recargo": True}, headers=auth("buyer")).json()
    assert r["erp_link"] == "no_link" and r["write_case"] == "pending_link" and r["cost"]["cost_with_recargo"] == "10.0000"


def test_net_entry_with_unknown_vat_is_refused_but_a_gross_one_gets_a_warning(client, engine):
    sid = seed(engine, vat=None)
    bad = client.post("/costs", json={"product_id": 1, "supplier_id": sid, "amount": "10", "includes_recargo": False}, headers=auth("buyer"))
    assert bad.status_code == 422 and "vat_unknown" in bad.json()["detail"]
    ok = client.post("/costs", json={"product_id": 1, "supplier_id": sid, "amount": "10", "includes_recargo": True}, headers=auth("buyer"))
    assert ok.status_code == 201 and ok.json()["warnings"] == ["vat_unknown"]


def test_input_validation(client, engine):
    sid = seed(engine)
    for body in [{"product_id": 1, "supplier_id": "nope", "amount": "1", "includes_recargo": True},
                 {"product_id": 1, "supplier_id": sid, "amount": "-1", "includes_recargo": True},
                 {"product_id": 0, "supplier_id": sid, "amount": "1", "includes_recargo": True}]:
        assert client.post("/costs", json=body, headers=auth("buyer")).status_code == 422


def test_jump_blocks_then_confirm_and_verify_flow(client, engine):
    sid = seed(engine)
    mk = lambda amount: client.post("/costs", json={"product_id": 1, "supplier_id": sid, "amount": amount, "includes_recargo": True}, headers=auth("buyer")).json()  # noqa: E731
    mk("10")
    jump = mk("20")
    assert jump["warnings"] == ["abnormal_jump"] and jump["cost"]["status"] == "blocked_jump"
    issues = client.get("/costs?only_issues=true", headers=auth()).json()
    assert [c["id"] for c in issues] == [jump["cost"]["id"]]
    assert client.post(f"/costs/{jump['cost']['id']}/confirm-jump", headers=auth("buyer")).status_code == 204
    assert client.get("/costs?only_issues=true", headers=auth()).json() == []
    assert client.post(f"/costs/{jump['cost']['id']}/verify", headers=auth("buyer")).status_code == 204
    assert client.post("/costs/missing/verify", headers=auth("buyer")).status_code == 404
    assert client.get(f"/costs?product_id=1&supplier_id={sid}", headers=auth()).json()[0]["version"] == 2    # only the current version is listed
    assert client.get("/audit/verify", headers=auth()).json()["ok"] is True


def test_terms_are_versioned_and_validated(client, engine):
    sid = seed(engine)
    body = {"min_order_value": "150.00", "min_qty_for_delivery": 5, "free_delivery_threshold": "300", "delivery_charge": "9.5", "order_days": [1, 3], "delivery_schedule": "48 h"}
    assert client.put(f"/suppliers/{sid}/terms", json=body, headers=auth("buyer")).json() == {"version": 1}
    assert client.put(f"/suppliers/{sid}/terms", json={**body, "delivery_charge": "12"}, headers={**auth("buyer"), "If-Match": '"1"'}).json() == {"version": 2}
    s = client.get("/suppliers", headers=auth()).json()[0]
    assert s["terms"]["delivery_charge"] == "12.0000" and s["terms"]["order_days"] == [1, 3]
    for bad in [{**body, "order_days": [0]}, {**body, "order_days": [1, 1]}, {**body, "min_order_value": "-1"}, {**body, "free_delivery_threshold": "10"}]:
        assert client.put(f"/suppliers/{sid}/terms", json=bad, headers=auth("buyer")).status_code == 422
    assert client.put("/suppliers/unknown/terms", json=body, headers=auth("buyer")).status_code == 422


def test_price_list_upload_all_or_nothing(client, engine):
    sid = seed(engine)
    good = b"variant_id;cost;includes_recargo;pack_size;lead_time_days;min_order_qty\n10;100;no;12;3;6\n"
    r = client.post("/costs/import", data={"supplier_id": sid}, files={"file": ("lista.csv", io.BytesIO(good))}, headers=auth("buyer"))
    assert r.status_code == 200 and r.json()["applied"] == 1 and r.json()["errors"] == []
    bad = good + b"99;1;si;;;\n"
    r2 = client.post("/costs/import", data={"supplier_id": sid}, files={"file": ("lista.csv", io.BytesIO(bad))}, headers=auth("buyer")).json()
    assert r2["applied"] == 0 and r2["errors"] == [{"row": 3, "column": "variant_id", "code": "unknown_variant"}]
    assert len(client.get("/costs", headers=auth()).json()) == 1
    assert client.post("/costs/import", data={"supplier_id": sid}, files={"file": ("lista.pdf", io.BytesIO(b"x"))}, headers=auth("buyer")).status_code == 422
    assert client.post("/costs/import", data={"supplier_id": "nope"}, files={"file": ("lista.csv", io.BytesIO(good))}, headers=auth("buyer")).status_code == 422


def test_vat_is_buyer_maintained_per_product(client, engine):
    seed(engine, vat=None)
    assert client.put("/products/1/vat", json={"vat_rate": "10"}, headers=auth("viewer")).status_code == 403
    assert client.put("/products/1/vat", json={"vat_rate": "10"}, headers=auth("buyer")).json() == {"product_id": 1, "vat_rate": "10"}
    assert client.put("/products/1/vat", json={"vat_rate": "150"}, headers=auth("buyer")).status_code == 422
    assert client.put("/products/999/vat", json={"vat_rate": "10"}, headers=auth("buyer")).status_code == 404
