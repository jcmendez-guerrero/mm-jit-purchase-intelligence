"""T062: margin evaluation on the request, blocking below 15 %, and the admin override with a different releaser."""

from datetime import timedelta
from decimal import Decimal

import pytest
from builders import FakeLots
from conftest import NOW, add_product, add_supplier
from costs.lot_costs import record_lot_cost
from costs.median_suggestion import request_median_write
from costs.writes import WriteError, approve_write, awaiting_other_buyer, set_override, writer_view
from db.tables import audit_events, erp_supplier_links, user_roles
from mmi_common.auth import Principal
from sqlalchemy import insert, select

D = Decimal


class Blob:
    def __init__(self, tmp):
        self.tmp = tmp

    def put(self, name, data):
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()


class Pvp:
    def __init__(self, price):
        self.price = price

    def prices(self, ids):
        return {} if self.price is None else {1: D(self.price)}


def who(name, roles, minutes=1):
    return Principal(name, frozenset(roles), NOW - timedelta(minutes=minutes))


@pytest.fixture
def blocked(conn, tmp_path):
    """Median 9.00 against PVP 10.00: margin 10 % < 15 %."""
    sid = add_supplier(conn)
    add_product(conn, 1, 10, vat=D("21"))
    conn.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=sid, has_cost=False, last_seen_at=NOW))
    record_lot_cost(conn, Blob(tmp_path), variant_id=1, supplier_id=sid, lot="L1", unit_cost=D("9.00"), source="confirmed_order", actor="system", quantity=3, now=NOW)
    req = request_median_write(conn, FakeLots([{"variant_id": 1, "lot": "L1", "quantity": 3}]), 10, sid, "receipt_matched", "system", NOW, Pvp("10.00")).request
    return req, sid


def test_the_request_records_pvp_margins_and_flags(blocked):
    req, _ = blocked
    assert D(str(req.pvp_used)) == D("10.00") and D(str(req.margin_after)) == D("0.1000") and req.rule_flags == ["margin_below_minimum"]


def test_a_blocked_request_cannot_be_released_by_a_buyer(conn, blocked, tmp_path):
    req, _ = blocked
    with pytest.raises(WriteError) as e:
        approve_write(conn, req.id, who("buyer-1", {"buyer"}), Blob(tmp_path), now=NOW)
    assert e.value.code == "margin_below_minimum"


def test_only_an_admin_can_override_with_a_reason_and_a_non_negative_value(conn, blocked):
    req, _ = blocked
    for p in (who("buyer-1", {"buyer"}), who("approver-1", {"approver"})):
        with pytest.raises(WriteError) as e:
            set_override(conn, req.id, p, D("8.00"), "oferta del proveedor", NOW)
        assert e.value.code == "not_an_admin"
    admin = who("admin-1", {"admin"})
    for reason in ("", "  ", "no"):
        with pytest.raises(WriteError) as e2:
            set_override(conn, req.id, admin, D("8.00"), reason, NOW)
        assert e2.value.code == "override_reason_required"
    with pytest.raises(WriteError) as e3:
        set_override(conn, req.id, admin, D("-1"), "valor erroneo", NOW)
    assert e3.value.code == "negative_value"


def test_the_override_replaces_the_value_recomputes_the_margin_and_is_audited(conn, blocked):
    req, _ = blocked
    out = set_override(conn, req.id, who("admin-1", {"admin"}), D("8.50"), "oferta puntual del proveedor", NOW)
    assert D(str(out.proposed_value)) == D("8.5000") and D(str(out.median_cost)) == D("9.00") and D(str(out.margin_after)) == D("0.1500")
    assert "override" in out.rule_flags and "margin_below_minimum" not in out.rule_flags
    entry = conn.execute(select(audit_events).where(audit_events.c.action == "cost_write.override_set")).one()
    text = str(entry.after) + str(entry.before)
    assert "oferta puntual" in text and "8.5" in text and "9.00" in text and "admin-1" in text and "0.1500" in text


def test_the_person_who_set_the_override_cannot_release_it_but_a_different_buyer_can(conn, blocked, tmp_path):
    req, _ = blocked
    set_override(conn, req.id, who("both-1", {"admin", "buyer"}), D("8.50"), "oferta puntual del proveedor", NOW)
    with pytest.raises(WriteError) as e:
        approve_write(conn, req.id, who("both-1", {"admin", "buyer"}), Blob(tmp_path), now=NOW)
    assert e.value.code == "override_release_same_person"
    with pytest.raises(WriteError) as e2:
        approve_write(conn, req.id, who("buyer-2", {"buyer"}, minutes=30), Blob(tmp_path), now=NOW)
    assert e2.value.code == "mfa_required"                                             # still needs a fresh second factor
    released = approve_write(conn, req.id, who("buyer-2", {"buyer"}), Blob(tmp_path), now=NOW)
    assert released.status == "approved_by_buyer" and released.released_by == "buyer-2" and released.override_by == "both-1"
    assert D(str(released.proposed_value)) == D("8.5000")


def test_the_writer_still_sees_only_the_released_value_and_the_same_fields(conn, blocked, tmp_path):
    req, _ = blocked
    set_override(conn, req.id, who("admin-1", {"admin"}), D("8.50"), "oferta puntual del proveedor", NOW)
    assert writer_view(conn, req.id) is None                                           # not released: the writer acts on nothing
    approve_write(conn, req.id, who("buyer-2", {"buyer"}), Blob(tmp_path), now=NOW)
    view = writer_view(conn, req.id)
    assert view["cents"] == 850 and set(view) == {"id", "status", "product_id", "supplier_id", "cents", "previous_cents", "idempotency_key", "supplier_contact_id"}


def test_the_override_stays_pending_when_no_other_buyer_exists(conn, blocked):
    req, _ = blocked
    set_override(conn, req.id, who("both-1", {"admin", "buyer"}), D("8.50"), "oferta puntual del proveedor", NOW)
    conn.execute(insert(user_roles).values(user_id="both-1", roles=["admin", "buyer"], active=True, updated_by="t", updated_at=NOW))
    assert awaiting_other_buyer(conn, req.id) is True
    conn.execute(insert(user_roles).values(user_id="buyer-2", roles=["buyer"], active=True, updated_by="t", updated_at=NOW))
    assert awaiting_other_buyer(conn, req.id) is False


def test_an_override_is_refused_once_the_request_was_released(conn, blocked, tmp_path):
    req, _ = blocked
    admin = who("admin-1", {"admin"})
    set_override(conn, req.id, admin, D("8.50"), "oferta puntual del proveedor", NOW)
    approve_write(conn, req.id, who("buyer-2", {"buyer"}), Blob(tmp_path), now=NOW)
    with pytest.raises(WriteError) as e:
        set_override(conn, req.id, admin, D("8.00"), "cambio tardio de valor", NOW)
    assert e.value.code == "cannot_override_from_approved_by_buyer"


def test_without_a_pvp_the_margin_is_unavailable_and_the_release_is_blocked_until_an_admin_overrides(conn, tmp_path):
    sid = add_supplier(conn)
    add_product(conn, 1, 10, vat=D("21"))
    conn.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=sid, has_cost=False, last_seen_at=NOW))
    record_lot_cost(conn, Blob(tmp_path), variant_id=1, supplier_id=sid, lot="L1", unit_cost=D("9.00"), source="confirmed_order", actor="system", quantity=3, now=NOW)
    req = request_median_write(conn, FakeLots([{"variant_id": 1, "lot": "L1", "quantity": 3}]), 10, sid, "receipt_matched", "system", NOW, Pvp(None)).request
    assert req.rule_flags == ["margin_unavailable"] and req.margin_after is None
    with pytest.raises(WriteError) as e:
        approve_write(conn, req.id, who("buyer-1", {"buyer"}), Blob(tmp_path), now=NOW)
    assert e.value.code == "margin_unavailable"
    set_override(conn, req.id, who("admin-1", {"admin"}), D("9.00"), "precio de venta pendiente de alta", NOW)
    assert approve_write(conn, req.id, who("buyer-1", {"buyer"}), Blob(tmp_path), now=NOW).status == "approved_by_buyer"


def test_a_pvp_lookup_failure_builds_no_request(conn, tmp_path):
    from costs.lot_lookup import LotLookupError

    sid = add_supplier(conn)
    add_product(conn, 1, 10)
    record_lot_cost(conn, Blob(tmp_path), variant_id=1, supplier_id=sid, lot="L1", unit_cost=D("9.00"), source="confirmed_order", actor="system", quantity=3, now=NOW)

    class Down:
        def prices(self, ids):
            raise ConnectionError

    with pytest.raises(LotLookupError) as e:
        request_median_write(conn, FakeLots([{"variant_id": 1, "lot": "L1", "quantity": 3}]), 10, sid, "receipt_matched", "system", NOW, Down())
    assert e.value.code == "pvp_unavailable"
