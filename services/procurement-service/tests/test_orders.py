"""T098 / T099: order confirmation, inbound projection and receipt reconciliation."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from approvals.workflow import decide, submit
from builders import flat_forecast, inputs, offer, terms, variant
from conftest import NOW, add_supplier
from costs.rules import CostRules
from costs.store import NewCost, add_version, current
from db.tables import erp_supplier_links, inbound_order_lines, inbound_orders, outbox, receipt_matches
from mmi_common.auth import Principal
from orders.confirm import ConfirmLine, OrderError, confirm_order, open_inbound
from orders.reconcile import Receipt, parse_purchase_ref, reconcile_receipts
from proposals.generate import generate, store
from sqlalchemy import insert, select, update

D = Decimal


class Blob:
    def __init__(self, tmp):
        self.tmp = tmp

    def put(self, name, data):
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()


class Users:
    def active_approvers(self):
        return {"approver-2"}


@pytest.fixture
def approved(conn):
    """An approved proposal with one line for supplier A (variant 1 / product 10) and one for B."""
    sa, sb = add_supplier(conn, 1, "A"), add_supplier(conn, 2, "B")
    for sid, cost in ((sa, "1.00"), (sb, "2.00")):
        add_version(conn, NewCost(product_id=10, supplier_id=sid, cost_with_recargo=D(cost), source="siweb_product_supplier", actor="siweb-import"), CostRules(), NOW)
        conn.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=sid, has_cost=True, last_seen_at=NOW))
    d = generate(inputs([variant(1, [offer(sa, "1.00")], flat_forecast(1.0)), variant(2, [offer(sb, "2.00")], flat_forecast(1.0))], [terms(sa), terms(sb)]), 10)
    pid = store(conn, d, "buyer-1", "2026-W46", None, NOW)
    submit(conn, pid, "buyer-1", 1, Users(), NOW)
    decide(conn, pid, Principal("approver-2", frozenset({"approver"}), NOW - timedelta(minutes=1)), 1, now=NOW)
    return pid, sa, sb


def lines_of(conn, pid, sid):
    from db.tables import proposal_lines

    return conn.execute(select(proposal_lines).where(proposal_lines.c.proposal_id == pid, proposal_lines.c.supplier_id == sid)).all()


def test_confirming_records_actual_quantities_and_costs_and_announces_the_inbound(conn, approved, tmp_path):
    pid, sa, _sb = approved
    ln = lines_of(conn, pid, sa)[0]
    res = confirm_order(conn, pid, sa, [ConfirmLine(1, ln.qty + 2, D("1.00"))], "buyer-1", Blob(tmp_path), NOW)
    o = conn.execute(select(inbound_orders)).one()
    assert (o.status, o.supplier_id, o.confirmed_by) == ("confirmed", sa, "buyer-1") and res.cost_writes == []     # same cost as the ERP: no write
    il = conn.execute(select(inbound_order_lines)).one()
    assert (il.qty, il.received_qty, D(str(il.confirmed_cost_with_recargo))) == (ln.qty + 2, 0, D("1.0000"))
    env = conn.execute(select(outbox)).all()[-1].envelope
    assert env["type"] == "procurement.order.confirmed.v1" and env["resource_id"] == res.order_id


def test_a_different_cost_creates_a_new_version_and_a_write_request_for_review(conn, approved, tmp_path):
    pid, sa, _sb = approved
    res = confirm_order(conn, pid, sa, [ConfirmLine(1, 10, D("1.10"))], "buyer-1", Blob(tmp_path), NOW)
    assert len(res.cost_writes) == 1 and res.cost_writes[0].status == "pending_review"
    cur = current(conn, 10, sa)
    assert cur.source == "manual" and D(str(cur.cost_with_recargo)) == D("1.1000") and cur.version == 2
    assert D(str(res.cost_writes[0].request.previous_siweb_value)) == D("1.0000") and "pending_review" not in res.warnings


def test_a_confirmed_price_that_looks_like_a_jump_is_accepted_because_the_buyer_agreed_it(conn, approved, tmp_path):
    pid, sa, _sb = approved
    res = confirm_order(conn, pid, sa, [ConfirmLine(1, 10, D("5.00"))], "buyer-1", Blob(tmp_path), NOW)
    cur = current(conn, 10, sa)
    assert cur.jump_flag and cur.jump_confirmed_by == "buyer-1" and "cost_jump_confirmed:1" in res.warnings


def test_zero_quantity_lines_are_not_inbound_and_one_order_per_supplier(conn, approved, tmp_path):
    pid, sa, _sb = approved
    confirm_order(conn, pid, sa, [ConfirmLine(1, 0, D("1.00"))], "buyer-1", Blob(tmp_path), NOW)
    assert conn.execute(select(inbound_order_lines)).all() == []
    with pytest.raises(OrderError) as e:
        confirm_order(conn, pid, sa, [ConfirmLine(1, 5, D("1.00"))], "buyer-1", Blob(tmp_path), NOW)
    assert e.value.code == "already_confirmed"


def test_confirmation_validates_the_lines(conn, approved, tmp_path):
    pid, sa, _sb = approved
    for lines, code in [([ConfirmLine(99, 1, D("1"))], "line_not_in_proposal:99"), ([ConfirmLine(2, 1, D("1"))], "line_not_in_proposal:2"),
                        ([ConfirmLine(1, 1, D("1")), ConfirmLine(1, 2, D("1"))], "duplicate_line:1"), ([ConfirmLine(1, -1, D("1"))], "negative_value")]:
        with pytest.raises(OrderError) as e:
            confirm_order(conn, pid, sa, lines, "buyer-1", Blob(tmp_path), NOW)
        assert e.value.code == code
    with pytest.raises(OrderError) as e:
        confirm_order(conn, pid, "nope", [ConfirmLine(1, 1, D("1"))], "buyer-1", Blob(tmp_path), NOW)
    assert e.value.code == "supplier_not_in_proposal" and conn.execute(select(inbound_orders)).all() == []


def test_open_inbound_feeds_the_next_proposal_with_remaining_quantities_and_eta(conn, approved, tmp_path):
    pid, sa, _sb = approved
    confirm_order(conn, pid, sa, [ConfirmLine(1, 10, D("1.00"))], "buyer-1", Blob(tmp_path), NOW, expected_delivery=date(2026, 11, 12))
    assert open_inbound(conn, date(2026, 11, 9)) == {1: [(10, 3)]}
    conn.execute(update(inbound_order_lines).values(received_qty=4))
    assert open_inbound(conn, date(2026, 11, 9)) == {1: [(6, 3)]}


# ---- receipts --------------------------------------------------------------------------------------------

def test_purchase_reference_formats():
    assert [parse_purchase_ref(x) for x in ("123", " 7 ", "Compra #45", "compra#9", "COMPRA # 12", 88)] == [123, 7, 45, 9, 12, 88]
    assert [parse_purchase_ref(x) for x in (None, "", "Factura 3", "Compra #", "12a")] == [None] * 5


def order_with(conn, tmp_path, approved, qty=10, ref=None):
    pid, sa, _sb = approved
    confirm_order(conn, pid, sa, [ConfirmLine(1, qty, D("1.00"))], "buyer-1", Blob(tmp_path), NOW, erp_purchase_ref=ref)
    return pid, sa


def test_a_receipt_is_matched_once_and_updates_the_order_status(conn, approved, tmp_path):
    order_with(conn, tmp_path, approved)
    r = reconcile_receipts(conn, [Receipt(100, 1, 4, "Compra #77")], NOW)
    assert r.matched == 1 and conn.execute(select(inbound_order_lines.c.received_qty)).scalar_one() == 4
    assert conn.execute(select(inbound_orders.c.status)).scalar_one() == "partially_received"
    again = reconcile_receipts(conn, [Receipt(100, 1, 4, "Compra #77")], NOW)                                      # same movement re-collected
    assert again.already_applied == 1 and conn.execute(select(inbound_order_lines.c.received_qty)).scalar_one() == 4
    reconcile_receipts(conn, [Receipt(101, 1, 6, "77")], NOW)
    assert conn.execute(select(inbound_orders.c.status)).scalar_one() == "received" and open_inbound(conn, date(2026, 11, 9)) == {}


def test_receipt_beyond_the_order_is_reported_not_added(conn, approved, tmp_path):
    order_with(conn, tmp_path, approved, qty=5)
    r = reconcile_receipts(conn, [Receipt(100, 1, 8, None)], NOW)
    assert r.excess == [(100, 3)] and conn.execute(select(inbound_order_lines.c.received_qty)).scalar_one() == 5
    assert conn.execute(select(receipt_matches.c.qty)).scalar_one() == 5


def test_unmatched_and_non_positive_receipts_are_listed(conn, approved, tmp_path):
    order_with(conn, tmp_path, approved)
    r = reconcile_receipts(conn, [Receipt(1, 2, 3, None), Receipt(2, 1, -1, None), Receipt(3, 1, 0, None)], NOW)
    assert r.unmatched == [(1, "no_open_order"), (2, "not_a_receipt"), (3, "not_a_receipt")] and r.matched == 0


def test_an_erp_purchase_number_pins_the_receipt_to_its_order_otherwise_oldest_first(conn, approved, tmp_path):
    pid, sa, _sb = approved
    d2 = generate(inputs([variant(1, [offer(sa, "1.00")], flat_forecast(2.0))], [terms(sa)]), 10)
    pid2 = store(conn, d2, "buyer-1", "2026-W47", None, NOW + timedelta(days=7))
    submit(conn, pid2, "buyer-1", 1, Users(), NOW)
    decide(conn, pid2, Principal("approver-2", frozenset({"approver"}), NOW - timedelta(minutes=1)), 1, now=NOW)
    confirm_order(conn, pid, sa, [ConfirmLine(1, 10, D("1.00"))], "buyer-1", Blob(tmp_path), NOW, erp_purchase_ref=11)
    confirm_order(conn, pid2, sa, [ConfirmLine(1, 10, D("1.00"))], "buyer-1", Blob(tmp_path), NOW + timedelta(days=7), erp_purchase_ref=22)
    reconcile_receipts(conn, [Receipt(1, 1, 4, "Compra #22")], NOW)
    got = {r.order_id: r.received_qty for r in conn.execute(select(inbound_order_lines)).all()}
    orders = {r.erp_purchase_ref: r.id for r in conn.execute(select(inbound_orders)).all()}
    assert got[orders[22]] == 4 and got[orders[11]] == 0
    reconcile_receipts(conn, [Receipt(2, 1, 5, None)], NOW)                                                          # no reference: FIFO -> oldest order
    got = {r.order_id: r.received_qty for r in conn.execute(select(inbound_order_lines)).all()}
    assert got[orders[11]] == 5
