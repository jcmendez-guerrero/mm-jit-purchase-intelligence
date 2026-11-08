"""T146 / T148 / T149 / T150: procurement-in consumer, supplier-row ingestion, receipt polling and the worker pass."""

import json
import uuid
from datetime import timedelta
from decimal import Decimal

from conftest import NOW, add_supplier
from consumer import consume_once, supplier_rows_from_payload, sync_receipts
from costs.rules import CostRules
from costs.store import NewCost, add_version, current
from costs.writes import request_write
from db.tables import cost_write_requests, forecast_runs_seen, outbox, receipt_cursor, suppliers
from mmi_common.bus import POISON_SUFFIX, InMemoryBus, new_envelope
from sqlalchemy import func, insert, select
from worker import FileBlobs, run_once

D = Decimal


def announce(bus, tmp_path, type_, doc):
    data = json.dumps(doc).encode()
    p = tmp_path / f"{uuid.uuid4()}.json"
    p.write_bytes(data)
    env = new_envelope(type_, str(uuid.uuid4()), data, p.as_uri(), str(uuid.uuid4()))
    bus.send("procurement-in", env)
    return env


def count(engine, table):
    with engine.connect() as c:
        return c.execute(select(func.count()).select_from(table)).scalar_one()


def test_supplier_rows_never_carry_the_tax_identifier_and_convert_cents():
    rows = supplier_rows_from_payload({"records": [{"product_id": 1, "contact_id": 9, "supplier_name": "P", "supplier_cif": "A00000000", "purchase_cost_cents": 1052.5,
                                                    "lead_time_days": 3, "min_order_qty": 2}, {"product_id": 2, "contact_id": 9, "purchase_cost_cents": None}]})
    assert rows[0]["purchase_cost"] == D("10.525") and "supplier_cif" not in rows[0] and rows[1]["purchase_cost"] is None


def test_supplier_cost_syncs_create_suppliers_costs_and_erp_links(engine, tmp_path):
    bus = InMemoryBus()
    announce(bus, tmp_path, "siweb.sync.completed.v1", {"kind": "supplier_costs", "records": [
        {"product_id": 1, "contact_id": 9, "supplier_name": "Proveedor Sintetico", "supplier_cif": "A00000000", "purchase_cost_cents": 1000},
        {"product_id": 2, "contact_id": 9, "supplier_name": "Proveedor Sintetico", "purchase_cost_cents": None}]})
    announce(bus, tmp_path, "siweb.sync.completed.v1", {"kind": "movements", "records": []})                   # other kinds are acknowledged
    stats = consume_once(engine, bus, FileBlobs())
    assert stats.applied == 2 and stats.rejected == 0
    with engine.connect() as c:
        sid = c.execute(select(suppliers.c.id)).scalar_one()
        assert D(str(current(c, 1, sid).cost_with_recargo)) == D("10.0000") and current(c, 2, sid) is None
    assert "A00000000" not in str(engine.connect().execute(select(suppliers)).all())


def test_forecast_completed_is_recorded_once(engine, tmp_path):
    bus = InMemoryBus()
    for _ in range(2):
        announce(bus, tmp_path, "forecast.completed.v1", {"run_id": "run-1", "input_hash": "h" * 64, "eligible_count": 7})
    consume_once(engine, bus, FileBlobs())
    assert count(engine, forecast_runs_seen) == 1


def test_a_writer_outcome_updates_the_request_and_unknown_requests_are_poisoned(engine, tmp_path):
    with engine.begin() as c:
        sid = add_supplier(c)
        from db.tables import erp_supplier_links

        c.execute(insert(erp_supplier_links).values(product_id=1, supplier_id=sid, has_cost=False, last_seen_at=NOW))
        cost = add_version(c, NewCost(product_id=1, supplier_id=sid, cost_with_recargo=D("5"), source="manual", actor="b"), CostRules(), NOW)
        rid = request_write(c, cost.id, "missing_cost", "b", NOW).request.id
    bus = InMemoryBus()
    announce(bus, tmp_path, "siweb.cost.write_completed.v1", {"cost_write_request_id": rid, "outcome": "retrying", "attempts": 2, "error": "HTTP 503"})
    announce(bus, tmp_path, "siweb.cost.write_completed.v1", {"cost_write_request_id": "nope", "outcome": "succeeded", "attempts": 1})
    stats = consume_once(engine, bus, FileBlobs())
    assert stats.applied == 1 and stats.rejected == 1 and bus.depth("procurement-in" + POISON_SUFFIX) == 1
    with engine.connect() as c:
        r = c.execute(select(cost_write_requests)).one()
    assert (r.status, r.attempts, r.last_error) == ("retrying", 2, "HTTP 503")


class Receipts:
    def __init__(self, items):
        self.items, self.calls = items, []

    def fetch_after(self, after_id):
        self.calls.append(after_id)
        return [x for x in self.items if x["movement_id"] > after_id]


def confirmed_order(engine, tmp_path):
    from approvals.workflow import decide, submit
    from builders import flat_forecast, inputs, offer, terms, variant
    from mmi_common.auth import Principal
    from orders.confirm import ConfirmLine, confirm_order
    from proposals.generate import generate, store

    class Users:
        def active_approvers(self):
            return {"approver-2"}

    class W:
        def put(self, n, d):
            return "file:///dev/null"

    with engine.begin() as c:
        sa = add_supplier(c)
        pid = store(c, generate(inputs([variant(1, [offer(sa, "1.00")], flat_forecast(1.0))], [terms(sa)]), 10), "buyer-1", "2026-W46", None, NOW)
        submit(c, pid, "buyer-1", 1, Users(), NOW)
        decide(c, pid, Principal("approver-2", frozenset({"approver"}), NOW - timedelta(minutes=1)), 1, now=NOW)
        confirm_order(c, pid, sa, [ConfirmLine(1, 10, D("1.00"))], "buyer-1", W(), NOW, erp_purchase_ref=77)


def test_receipts_are_polled_after_the_cursor_matched_and_never_applied_twice(engine, tmp_path):
    confirmed_order(engine, tmp_path)
    src = Receipts([{"movement_id": 5, "variant_id": 1, "qty": 4, "reference": "Compra #77"}, {"movement_id": 6, "variant_id": 9, "qty": 1, "reference": None}])
    with engine.begin() as c:
        out = sync_receipts(c, src, NOW)
    assert out == {"fetched": 2, "matched": 1, "unmatched": 1, "excess": 0, "cost_requests": 0}
    with engine.begin() as c:
        assert sync_receipts(c, src, NOW)["fetched"] == 0
        assert c.execute(select(receipt_cursor.c.last_movement_id)).scalar_one() == 6
    assert src.calls == [0, 6]


def test_worker_pass_consumes_reconciles_and_relays(engine, tmp_path):
    confirmed_order(engine, tmp_path)
    bus = InMemoryBus()
    announce(bus, tmp_path, "forecast.completed.v1", {"run_id": "run-2", "input_hash": "h" * 64, "eligible_count": 3})
    out = run_once(engine, bus, FileBlobs(), Receipts([{"movement_id": 1, "variant_id": 1, "qty": 10, "reference": 77}]))
    assert out["applied"] == 1 and out["receipts"]["matched"] == 1 and out["failed"] == 0 and out["relayed"] >= 1
    assert bus.depth("inventory-in") == 1                                                                         # procurement.order.confirmed.v1 reached inventory
    assert bus.receive("inventory-in", 1)[0].body["type"] == "procurement.order.confirmed.v1"
    with engine.connect() as c:
        assert all(r.status == "sent" for r in c.execute(select(outbox)).all())


def test_worker_without_an_inventory_url_skips_receipts(engine, tmp_path):
    out = run_once(engine, InMemoryBus(), FileBlobs(), None)
    assert out["receipts"] == {} and out["applied"] == 0
