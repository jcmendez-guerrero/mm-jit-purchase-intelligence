"""T032 (FR-016): a manual or imported cost never hides the ERP cost: the list shows both, who set the current one and when, and the difference.
The ERP version itself is never changed or removed.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from conftest import NOW, add_supplier  # noqa: F401
from costs.recargo import load_table
from costs.rules import CostRules
from costs.store import NewCost, add_version, history
from suppliers.links import LinkInput, list_links, put_link
from suppliers.service import SupplierInput, create_supplier
from suppliers_support import make_ref

D = Decimal
LATER = NOW + timedelta(days=1)


def supplier(conn):
    return create_supplier(conn, SupplierInput(name="Proveedor Sintetico", fiscal_type="national", country="ES", currency="EUR"), "buyer-1", now=NOW)


def erp_cost(conn, sid, value="2.00"):
    return add_version(conn, NewCost(product_id=10, supplier_id=sid, cost_with_recargo=D(value), source="siweb_product_supplier", actor="siweb-import"), CostRules(), NOW)


def manual(conn, sid, value, actor="buyer-2"):
    return put_link(conn, sid, "SYN-000001", LinkInput(cost=D(value), includes_recargo=True), actor, CostRules(), load_table(conn), now=LATER)


def one(conn, sid):
    rows = list_links(conn, sid)
    assert len(rows) == 1
    return rows[0]


def test_a_manual_cost_shows_the_erp_cost_beside_it_and_the_difference(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    erp_cost(conn, s.id, "2.00")
    manual(conn, s.id, "2.50")
    row = one(conn, s.id)
    assert (row["cost_source"], row["cost"]) == ("manual", "2.5000")
    assert (row["erp_cost"], row["cost_difference"], row["cost_difference_pct"]) == ("2.0000", "0.5000", "25.0")
    assert row["created_by"] == "buyer-2" and row["erp_verified_at"] and row["verified_at"]


def test_the_erp_version_is_neither_changed_nor_removed(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    erp = erp_cost(conn, s.id, "2.00")
    manual(conn, s.id, "2.50")
    versions = history(conn, 10, s.id, None)
    assert [v.source for v in versions] == ["siweb_product_supplier", "manual"]
    kept = versions[0]
    assert (kept.id, kept.cost_with_recargo, kept.source, kept.created_by) == (erp.id, erp.cost_with_recargo, "siweb_product_supplier", "siweb-import")
    assert kept.superseded_by == versions[1].id                                  # only the chain link moved: the manual version follows it


def test_a_cost_equal_to_the_erp_cost_has_no_difference(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    erp_cost(conn, s.id, "2.00")
    manual(conn, s.id, "2.00")
    row = one(conn, s.id)
    assert (row["erp_cost"], row["cost_difference"], row["cost_difference_pct"]) == ("2.0000", "0.0000", "0.0")


def test_when_the_current_cost_is_the_erp_cost_there_is_nothing_to_compare(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    erp_cost(conn, s.id, "2.00")
    row = one(conn, s.id)
    assert row["cost_source"] == "siweb_product_supplier" and row["erp_cost"] is None and row["cost_difference"] is None


def test_a_manual_cost_for_a_pair_the_erp_never_priced_has_no_erp_value_to_show(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    manual(conn, s.id, "2.50")
    row = one(conn, s.id)
    assert row["erp_cost"] is None and row["cost_difference"] is None and row["created_by"] == "buyer-2"


def test_the_latest_erp_value_is_the_one_compared(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    erp_cost(conn, s.id, "2.00")
    manual(conn, s.id, "2.50")
    add_version(conn, NewCost(product_id=10, supplier_id=s.id, cost_with_recargo=D("2.20"), source="siweb_product_supplier", actor="siweb-import"), CostRules(), LATER + timedelta(days=1))
    row = one(conn, s.id)
    assert row["cost_source"] == "siweb_product_supplier" and row["erp_cost"] is None            # the new ERP import is now the current one
