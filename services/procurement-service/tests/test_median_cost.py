"""T048 + T068: the median lot cost, the request it creates and when it is created."""

from decimal import Decimal

import pytest
from builders import FakeLots
from conftest import NOW, add_product, add_supplier
from costs.lot_costs import OPENING_LOT, record_lot_cost
from costs.median_suggestion import eligible_lots, lots_view, median_cost, request_median_write
from costs.writes import WriteError, approve_write
from db.tables import cost_write_requests, erp_supplier_links
from mmi_common.auth import Principal
from sqlalchemy import func, insert, select, update

D = Decimal


class Blob:
    def __init__(self, tmp):
        self.tmp = tmp

    def put(self, name, data):
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()


def test_median_odd_even_single_and_empty():
    assert median_cost([D("3"), D("1"), D("2")]) == D("2.00")
    assert median_cost([D("1.00"), D("2.00")]) == D("1.50")
    assert median_cost([D("5.1234")]) == D("5.12")
    assert median_cost([]) is None


def test_even_median_rounds_half_up_to_cents():
    assert median_cost([D("1.00"), D("1.0100")]) == D("1.01")       # 1.005 -> 1.01
    assert median_cost([D("2.0000"), D("2.0300")]) == D("2.02")     # 2.015 -> 2.02


@pytest.fixture
def pair(conn, tmp_path):
    sid = add_supplier(conn)
    add_product(conn, 1, 10, vat=D("21"))
    conn.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=sid, has_cost=False, last_seen_at=NOW))
    return sid


def lot(conn, tmp, sid, name, cost, source="confirmed_order", variant=1):
    record_lot_cost(conn, Blob(tmp), variant_id=variant, supplier_id=sid, lot=name, unit_cost=D(cost), source=source, actor="system:receipt-match", quantity=5, now=NOW)


def test_only_lots_with_stock_remaining_count_and_the_lots_used_are_stored(conn, pair, tmp_path):
    for name, cost in (("L1", "1.00"), ("L2", "3.00"), ("L3", "100.00")):
        lot(conn, tmp_path, pair, name, cost)
    stock = FakeLots([{"variant_id": 1, "lot": "L1", "quantity": 4}, {"variant_id": 1, "lot": "L2", "quantity": 2}, {"variant_id": 1, "lot": "L3", "quantity": 0}])
    res = request_median_write(conn, stock, 10, pair, "receipt_matched", "system:receipt-match", NOW)
    assert res.status == "pending_review" and D(str(res.request.median_cost)) == D("2.00") and D(str(res.request.proposed_value)) == D("2.00")
    assert sorted((x["lot"], x["quantity"]) for x in res.request.median_lot_refs) == [("L1", 4), ("L2", 2)]
    assert lots_view(conn, res.request.id)["median_cost"] == "2.00"


def test_nothing_in_stock_creates_no_request(conn, pair, tmp_path):
    lot(conn, tmp_path, pair, "L1", "1.00")
    res = request_median_write(conn, FakeLots([]), 10, pair, "receipt_matched", "system:receipt-match", NOW)
    assert res.request is None and res.status == "not_applicable" and res.warnings == ["no_lots_in_stock"]
    assert conn.execute(select(func.count()).select_from(cost_write_requests)).scalar() == 0


def test_stock_without_a_recorded_cost_is_ignored_not_guessed(conn, pair, tmp_path):
    stock = FakeLots([{"variant_id": 1, "lot": "UNKNOWN", "quantity": 9}, {"variant_id": 1, "lot": None, "quantity": 3}])
    assert eligible_lots(conn, stock, 10, pair) == []


def test_an_opening_entry_stands_in_when_the_erp_has_no_cost_and_nothing_else_qualifies(conn, pair, tmp_path):
    lot(conn, tmp_path, pair, OPENING_LOT, "1.40", source="buyer_entry")
    res = request_median_write(conn, FakeLots([]), 10, pair, "buyer_entry", "buyer-1", NOW)
    assert res.status == "pending_review" and D(str(res.request.median_cost)) == D("1.40")


def test_the_opening_entry_is_ignored_once_real_lots_qualify(conn, pair, tmp_path):
    lot(conn, tmp_path, pair, OPENING_LOT, "9.00", source="buyer_entry")
    lot(conn, tmp_path, pair, "L1", "1.00")
    res = request_median_write(conn, FakeLots([{"variant_id": 1, "lot": "L1", "quantity": 1}]), 10, pair, "receipt_matched", "system", NOW)
    assert D(str(res.request.median_cost)) == D("1.00")


def test_a_repeated_trigger_with_the_same_lots_returns_the_same_request(conn, pair, tmp_path):
    lot(conn, tmp_path, pair, "L1", "1.00")
    stock = FakeLots([{"variant_id": 1, "lot": "L1", "quantity": 1}])
    a = request_median_write(conn, stock, 10, pair, "receipt_matched", "system", NOW)
    b = request_median_write(conn, stock, 10, pair, "receipt_matched", "system", NOW)
    assert a.request.id == b.request.id


def buyer(minutes=1):
    from datetime import timedelta

    return Principal("buyer-1", frozenset({"buyer"}), NOW - timedelta(minutes=minutes))


def test_release_still_needs_the_buyer_a_fresh_second_factor_and_the_median(conn, pair, tmp_path):
    lot(conn, tmp_path, pair, "L1", "1.00")
    req = request_median_write(conn, FakeLots([{"variant_id": 1, "lot": "L1", "quantity": 1}]), 10, pair, "receipt_matched", "system", NOW).request
    with pytest.raises(WriteError) as e:
        approve_write(conn, req.id, Principal("viewer-1", frozenset({"viewer"}), NOW), Blob(tmp_path), now=NOW)
    assert e.value.code == "not_a_buyer"
    with pytest.raises(WriteError) as e2:
        approve_write(conn, req.id, buyer(30), Blob(tmp_path), now=NOW)
    assert e2.value.code == "mfa_required"
    conn.execute(update(cost_write_requests).where(cost_write_requests.c.id == req.id).values(proposed_value=D("1.99")))      # a value that is not the median
    with pytest.raises(WriteError) as e3:
        approve_write(conn, req.id, buyer(), Blob(tmp_path), now=NOW)
    assert e3.value.code == "median_required"
    conn.execute(update(cost_write_requests).where(cost_write_requests.c.id == req.id).values(proposed_value=D("1.00")))
    assert approve_write(conn, req.id, buyer(), Blob(tmp_path), now=NOW).status == "approved_by_buyer"


def test_the_request_exists_after_a_receipt_is_matched_and_not_before(conn, tmp_path):
    """T068 timing: confirming the order creates none; matching the receipt does."""
    from datetime import timedelta

    from approvals.workflow import decide, submit
    from builders import flat_forecast, inputs, offer, terms, variant
    from costs.rules import CostRules
    from costs.store import NewCost, add_version
    from db.tables import inbound_orders
    from orders.confirm import ConfirmLine, confirm_order
    from orders.reconcile import Receipt, reconcile_receipts
    from proposals.generate import generate, store

    class Users:
        def active_approvers(self):
            return {"approver-2"}

    sa = add_supplier(conn, 1, "A")
    add_product(conn, 1, 10, vat=D("21"))
    add_version(conn, NewCost(product_id=10, supplier_id=sa, cost_with_recargo=D("1.00"), source="siweb_product_supplier", actor="siweb-import"), CostRules(), NOW)
    conn.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=sa, has_cost=True, last_seen_at=NOW))
    pid = store(conn, generate(inputs([variant(1, [offer(sa, "1.00")], flat_forecast(1.0))], [terms(sa)]), 10), "buyer-1", "2026-W46", None, NOW)
    submit(conn, pid, "buyer-1", 1, Users(), NOW)
    decide(conn, pid, Principal("approver-2", frozenset({"approver"}), NOW - timedelta(minutes=1)), 1, now=NOW)
    res = confirm_order(conn, pid, sa, [ConfirmLine(1, 10, D("1.10"))], "buyer-1", Blob(tmp_path), NOW)
    assert res.cost_writes == [] and conn.execute(select(func.count()).select_from(cost_write_requests)).scalar() == 0
    out = reconcile_receipts(conn, [Receipt(1, 1, 10, None, "BATCH-7")], NOW, Blob(tmp_path))
    assert out.matched == 1 and out.pairs == {(1, sa)}
    req = request_median_write(conn, FakeLots([{"variant_id": 1, "lot": "BATCH-7", "quantity": 10}]), 10, sa, "receipt_matched", "system", NOW)
    assert D(str(req.request.median_cost)) == D("1.10") and conn.execute(select(inbound_orders.c.status)).scalar() == "received"
