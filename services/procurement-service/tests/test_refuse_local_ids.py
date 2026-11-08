"""T098/T099 (FR-003, FR-040, R1a): people use the SKU; ERP ids are resolved from it at send time, and a locally assigned id never reaches the ERP."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from approvals.workflow import ApprovalError  # noqa: F401 - keeps the workflow import path exercised
from conftest import NOW, add_supplier
from costs.directory import LOCAL_ID_FLOOR, SqlProductDirectory, is_local_id
from costs.recargo import load_table
from costs.rules import CostRules
from costs.store import NewCost, add_version
from costs.writes import WriteError, approve_write, request_write
from db.tables import erp_supplier_links, suppliers
from mmi_common.auth import Principal
from sqlalchemy import insert, update
from suppliers_support import make_ref

D = Decimal


class Blobs:
    def put(self, name, data):
        return "file:///dev/null"


def fresh_buyer():
    return Principal("buyer-1", frozenset({"buyer", "viewer"}), datetime.now(UTC))


def cost(conn, sid, product_id, source="manual"):
    return add_version(conn, NewCost(product_id=product_id, supplier_id=sid, cost_with_recargo=D("5.00"), source=source, actor="buyer-1"), CostRules(), NOW)


def test_the_floor_matches_the_loader_range():
    from export_loader.formats import SURROGATE_BASE

    assert LOCAL_ID_FLOOR == SURROGATE_BASE == 9_000_000
    assert is_local_id(9_000_000) and not is_local_id(8_999_999) and not is_local_id(None)


def test_a_sku_with_a_synced_real_id_resolves_to_it(conn):
    make_ref(conn, 1234, 56, "SYN-REAL")
    assert SqlProductDirectory(conn).erp_ids_for_sku("syn-real") == (56, 1234)


def test_a_sku_with_only_a_local_id_has_no_erp_ids(conn):
    make_ref(conn, 9_000_001, 9_000_001, "SYN-LOCAL")
    assert SqlProductDirectory(conn).erp_ids_for_sku("SYN-LOCAL") is None
    assert SqlProductDirectory(conn).erp_ids_for_sku("SYN-UNKNOWN") is None


def test_a_cost_write_for_a_local_product_is_parked_as_pending_link_even_if_a_link_row_exists(conn):
    sid = add_supplier(conn, 77, "ERP")
    make_ref(conn, 9_000_001, 9_000_001, "SYN-LOCAL")
    conn.execute(insert(erp_supplier_links).values(product_id=9_000_001, supplier_id=sid, has_cost=False, last_seen_at=NOW))
    c = cost(conn, sid, 9_000_001)
    res = request_write(conn, c.id, "missing_cost", "buyer-1", NOW)
    assert res.status == "pending_link"


def test_releasing_a_write_for_a_local_id_is_refused_as_pending_link(conn):
    sid = add_supplier(conn, 77, "ERP")
    conn.execute(insert(erp_supplier_links).values(product_id=9_000_001, supplier_id=sid, has_cost=False, last_seen_at=NOW))
    c = cost(conn, sid, 9_000_001)
    res = request_write(conn, c.id, "missing_cost", "buyer-1", NOW, median_cost=D("5.00"))
    with pytest.raises(WriteError) as e:
        approve_write(conn, res.request.id, fresh_buyer(), Blobs(), now=datetime.now(UTC))
    assert str(e.value) == "pending_link"


def test_releasing_a_write_for_a_supplier_with_a_local_or_unverified_contact_is_refused(conn):
    for contact, state in ((9_100_001, "linked"), (123456, "unverified")):
        sid = add_supplier(conn, contact, f"S{contact}")
        conn.execute(update(suppliers).where(suppliers.c.id == sid).values(erp_link_state=state))
        conn.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=sid, has_cost=False, last_seen_at=NOW))
        c = cost(conn, sid, 10)
        res = request_write(conn, c.id, "missing_cost", "buyer-1", NOW, median_cost=D("5.00"))
        with pytest.raises(WriteError) as e:
            approve_write(conn, res.request.id, fresh_buyer(), Blobs(), now=datetime.now(UTC))
        assert str(e.value) == "pending_link"


def test_an_ordinary_write_is_unaffected(conn):
    sid = add_supplier(conn, 123456, "ERP")
    conn.execute(update(suppliers).where(suppliers.c.id == sid).values(erp_link_state="linked"))
    conn.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=sid, has_cost=False, last_seen_at=NOW))
    c = cost(conn, sid, 10)
    assert request_write(conn, c.id, "missing_cost", "buyer-1", NOW).status == "pending_review"
    assert load_table(conn) is not None
