"""T047: the lot acquisition cost ledger."""

from decimal import Decimal

import pytest
from builders import FakeLots  # noqa: F401  (shared helper import keeps fixtures discoverable)
from conftest import NOW, add_product, add_supplier
from costs.lot_costs import OPENING_LOT, LotCostError, history, latest_by_lot, record_lot_cost, with_recargo
from db.tables import audit_events, lot_acquisition_costs, outbox
from sqlalchemy import func, select

D = Decimal


class Blob:
    def __init__(self, tmp):
        self.tmp = tmp

    def put(self, name, data):
        p = self.tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.as_uri()


def rec(conn, tmp, sid, lot="L1", cost="2.00", source="confirmed_order", **kw):
    return record_lot_cost(conn, Blob(tmp), variant_id=kw.pop("variant_id", 1), supplier_id=sid, lot=lot, unit_cost=D(cost), source=source, actor="buyer-1", now=NOW, **kw)


def test_net_entries_are_converted_to_recargo_inclusive_with_the_product_vat(conn):
    add_product(conn, 1, 10, vat=D("21"))
    assert with_recargo(conn, 1, D("100"), False) == D("105.2000")
    assert with_recargo(conn, 1, D("100"), True) == D("100.0000")


def test_unknown_vat_refuses_a_net_entry_but_not_a_gross_one(conn):
    add_product(conn, 1, 10, vat=None)
    with pytest.raises(LotCostError) as e:
        with_recargo(conn, 1, D("100"), False)
    assert e.value.code == "vat_unknown"
    assert with_recargo(conn, 1, D("100"), True) == D("100.0000")


def test_costs_are_non_negative_and_sources_are_limited(conn, tmp_path):
    sid = add_supplier(conn)
    with pytest.raises(LotCostError) as e:
        rec(conn, tmp_path, sid, cost="-0.01")
    assert e.value.code == "negative_cost"
    for bad in ("erp_movement", "pvp", ""):
        with pytest.raises(LotCostError) as e2:
            rec(conn, tmp_path, sid, source=bad)
        assert e2.value.code == "invalid_source"        # the ERP movement price (PVP) can never be a source
    with pytest.raises(LotCostError):
        rec(conn, tmp_path, sid, lot="  ")
    with pytest.raises(TypeError):
        record_lot_cost(conn, Blob(tmp_path), variant_id=1, supplier_id=sid, lot="L1", unit_cost=1.5, source="buyer_entry", actor="b", now=NOW)  # type: ignore[arg-type]
    assert conn.execute(select(func.count()).select_from(lot_acquisition_costs)).scalar() == 0


def test_a_correction_is_a_new_entry_the_latest_wins_and_history_is_kept(conn, tmp_path):
    from datetime import timedelta

    sid = add_supplier(conn)
    rec(conn, tmp_path, sid, cost="2.00")
    record_lot_cost(conn, Blob(tmp_path), variant_id=1, supplier_id=sid, lot="L1", unit_cost=D("2.50"), source="receipt_correction", actor="buyer-2", now=NOW + timedelta(minutes=5))
    assert latest_by_lot(conn, 1, sid)["L1"].unit_cost == D("2.5000")
    assert [h.source for h in history(conn, 1, sid, "L1")] == ["confirmed_order", "receipt_correction"]


def test_a_lot_bought_from_two_suppliers_has_two_independent_entries(conn, tmp_path):
    a, b = add_supplier(conn, 1, "A"), add_supplier(conn, 2, "B")
    rec(conn, tmp_path, a, cost="2.00")
    rec(conn, tmp_path, b, cost="3.00")
    assert latest_by_lot(conn, 1, a)["L1"].unit_cost == D("2.0000") and latest_by_lot(conn, 1, b)["L1"].unit_cost == D("3.0000")


def test_every_entry_is_audited_and_emits_an_event_that_carries_the_cost_for_the_inventory_projection(conn, tmp_path):
    sid = add_supplier(conn)
    rec(conn, tmp_path, sid, lot=OPENING_LOT, source="buyer_entry")
    assert conn.execute(select(func.count()).select_from(audit_events).where(audit_events.c.action == "lot_cost.recorded")).scalar() == 1
    ev = conn.execute(select(outbox)).all()
    assert [e.type for e in ev] == ["procurement.lot_cost.changed.v1"]
    import json

    payload = json.loads(next(iter(Blob(tmp_path).tmp.rglob("events/procurement.lot_cost.changed.v1/*.json"))).read_text())
    assert payload["unit_cost"] == "2.0000" and payload["source"] == "buyer_entry" and payload["lot"] == "opening"


def test_no_path_in_this_module_reads_the_erp_movement_price():
    import inspect

    import costs.lot_costs as m

    assert "unit_cost_pvp" not in inspect.getsource(m) and "stock_movements" not in inspect.getsource(m)
