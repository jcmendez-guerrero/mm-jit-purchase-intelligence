"""T100: an explicit merge moves what the merged supplier offers to the kept one, deactivates it with a pointer and is audited."""

from decimal import Decimal

import pytest
from audit.chain import verify_chain
from conftest import NOW
from costs.rules import CostRules
from costs.store import NewCost, add_version, current
from db.tables import audit_events, supplier_review_items, suppliers
from sqlalchemy import select
from suppliers.merge import MergeError, merge_suppliers, resolve_review_item
from suppliers.service import SupplierInput, create_supplier
from suppliers_support import open_line
from terms.service import Terms, current_terms, save_terms

D = Decimal


def supplier(conn, name, currency="EUR"):
    return create_supplier(conn, SupplierInput(name=name, fiscal_type="national", country="ES", currency=currency), "buyer-1", now=NOW)


def cost(conn, sid, pid, value, source="manual"):
    return add_version(conn, NewCost(product_id=pid, supplier_id=sid, cost_with_recargo=D(value), source=source, actor="buyer-1"), CostRules(), NOW)


def test_offers_terms_and_pointer_move_to_the_kept_supplier(conn):
    kept, gone = supplier(conn, "Proveedor Principal"), supplier(conn, "Proveedor principal sl")
    cost(conn, gone.id, 10, "3.00")
    cost(conn, gone.id, 20, "4.00")
    cost(conn, kept.id, 20, "5.00")                                    # the kept supplier already offers product 20: its cost stays
    save_terms(conn, gone.id, Terms(min_order_value=D("50")), "buyer-1", NOW)
    out = merge_suppliers(conn, gone.id, kept.id, "buyer-1", confirm=False, now=NOW)
    assert out == {"moved": 1, "kept_existing": 1, "terms_copied": True}
    assert current(conn, 10, kept.id).cost_with_recargo == D("3.0000") and current(conn, 20, kept.id).cost_with_recargo == D("5.0000")
    assert current(conn, 10, gone.id) is None and current(conn, 20, gone.id) is None
    assert current_terms(conn, kept.id).min_order_value == D("50.0000")
    row = conn.execute(select(suppliers).where(suppliers.c.id == gone.id)).one()
    assert (row.status, row.merged_into) == ("deactivated", kept.id)


def test_existing_terms_of_the_kept_supplier_are_not_overwritten(conn):
    kept, gone = supplier(conn, "A"), supplier(conn, "B")
    save_terms(conn, kept.id, Terms(min_order_value=D("10")), "buyer-1", NOW)
    save_terms(conn, gone.id, Terms(min_order_value=D("99")), "buyer-1", NOW)
    assert merge_suppliers(conn, gone.id, kept.id, "buyer-1", confirm=False, now=NOW)["terms_copied"] is False
    assert current_terms(conn, kept.id).min_order_value == D("10.0000")


def test_the_merge_is_audited_and_the_chain_stays_valid(conn):
    kept, gone = supplier(conn, "A"), supplier(conn, "B")
    merge_suppliers(conn, gone.id, kept.id, "admin-1", confirm=False, now=NOW)
    ev = [e for e in conn.execute(select(audit_events)).all() if e.action == "supplier.merged"]
    assert len(ev) == 1 and ev[0].actor == "admin-1" and ev[0].after["merged_into"] == kept.id
    assert verify_chain(conn).ok


@pytest.mark.parametrize(("a", "b", "code"), [("EUR", "USD", "merge_currency_mismatch")])
def test_different_currencies_are_refused(conn, a, b, code):
    kept, gone = supplier(conn, "A", a), supplier(conn, "B", b)
    with pytest.raises(MergeError) as exc:
        merge_suppliers(conn, gone.id, kept.id, "buyer-1", confirm=False, now=NOW)
    assert exc.value.code == code


def test_a_supplier_cannot_be_merged_into_itself_or_into_a_deactivated_one(conn):
    a, b = supplier(conn, "A"), supplier(conn, "B")
    with pytest.raises(MergeError) as exc:
        merge_suppliers(conn, a.id, a.id, "buyer-1", confirm=False, now=NOW)
    assert exc.value.code == "merge_same_supplier"
    merge_suppliers(conn, b.id, a.id, "buyer-1", confirm=False, now=NOW)
    with pytest.raises(MergeError) as exc:
        merge_suppliers(conn, a.id, b.id, "buyer-1", confirm=False, now=NOW)
    assert exc.value.code == "supplier_deactivated"


def test_open_proposal_lines_need_a_confirmation_and_are_then_flagged(conn):
    kept, gone = supplier(conn, "A"), supplier(conn, "B")
    open_line(conn, gone.id, 1, "draft")
    with pytest.raises(MergeError) as exc:
        merge_suppliers(conn, gone.id, kept.id, "buyer-1", confirm=False, now=NOW)
    assert exc.value.code == "merge_open_lines" and exc.value.open_lines == 1
    assert conn.execute(select(suppliers.c.status).where(suppliers.c.id == gone.id)).scalar() == "active"
    merge_suppliers(conn, gone.id, kept.id, "buyer-1", confirm=True, now=NOW)
    kinds = [i.kind for i in conn.execute(select(supplier_review_items)).all()]
    assert kinds == ["proposal_reallocation"]


def test_resolving_a_duplicate_item_with_merge_runs_the_merge(conn):
    kept = supplier(conn, "Proveedor Alfa")
    gone = create_supplier(conn, SupplierInput(name="PROVEEDOR ALFA", fiscal_type="national", country="ES", currency="EUR"), "b", confirm_duplicate=True, now=NOW)
    item = conn.execute(select(supplier_review_items)).one()
    resolve_review_item(conn, item.id, "merge_into", "buyer-1", merge_into=kept.id, now=NOW)
    assert conn.execute(select(suppliers.c.merged_into).where(suppliers.c.id == gone.id)).scalar() == kept.id
    assert conn.execute(select(supplier_review_items.c.status)).scalar() == "resolved"


def test_keep_both_and_ignore_close_the_item_without_touching_suppliers(conn):
    supplier(conn, "Proveedor Alfa")
    create_supplier(conn, SupplierInput(name="PROVEEDOR ALFA", fiscal_type="national", country="ES", currency="EUR"), "b", confirm_duplicate=True, now=NOW)
    item = conn.execute(select(supplier_review_items)).one()
    resolve_review_item(conn, item.id, "keep_both", "buyer-1", now=NOW)
    assert conn.execute(select(supplier_review_items.c.status)).scalar() == "resolved"
    assert conn.execute(select(suppliers.c.status)).scalars().all() == ["active", "active"]
    with pytest.raises(MergeError) as exc:
        resolve_review_item(conn, item.id, "ignore", "buyer-1", now=NOW)
    assert exc.value.code == "review_item_closed"
