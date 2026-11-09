"""T013: what a buyer saves persists. Suppliers, terms versions and links are committed, then read back in a new transaction unchanged
(CRUD persists, FR-003). Duplicate-name warnings are covered in test_suppliers_service.py.

Limit: the test engine is one shared in-memory SQLite connection, so this proves committed state, not isolation between database connections;
that needs the PostgreSQL integration run (T049).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from conftest import NOW
from costs.recargo import load_table
from costs.rules import CostRules
from suppliers.links import LinkInput, list_links, put_link
from suppliers.service import (
    SupplierInput,
    create_supplier,
    deactivate_supplier,
    get_supplier,
    reactivate_supplier,
    update_supplier,
)
from suppliers_support import make_ref
from terms.service import Discount, Terms, current_terms, history, save_terms

D = Decimal

TERMS = Terms(min_order_value=D("150.00"), free_delivery_threshold=D("300.00"), delivery_charge=D("9.50"), order_days=(1, 4), lead_time_days=3,
              delivery_weekdays=(2, 5), order_cutoff_time="13:30", payment_terms_days=30, preferred=True,
              discounts=(Discount("percent", "order_value", D("500"), D("3")),))


def test_a_supplier_with_terms_and_a_link_reads_back_identically_from_a_new_connection(engine):
    with engine.begin() as c:
        make_ref(c, 1, 10, "SYN-000001")
        s = create_supplier(c, SupplierInput(name="Proveedor Sintetico Persistente", fiscal_type="national", country="ES", currency="EUR",
                                             payment_terms_days=30, order_channel="email"), "buyer-1", now=NOW)
        sid = s.id
        save_terms(c, sid, TERMS, "buyer-1", now=NOW, reason="alta inicial")
        put_link(c, sid, "SYN-000001", LinkInput(cost=D("12.34"), includes_recargo=False, pack_size=6, min_qty=12), "buyer-1", CostRules(), load_table(c), now=NOW)

    with engine.begin() as c:                                    # a different connection and transaction
        row = get_supplier(c, sid)
        assert (row.name, row.currency, row.payment_terms_days, row.order_channel, row.status, row.version) == (
            "Proveedor Sintetico Persistente", "EUR", 30, "email", "active", 1)
        got = current_terms(c, sid, as_of=datetime(2026, 11, 9, tzinfo=UTC))
        assert got == TERMS and isinstance(got.min_order_value, Decimal)
        assert [(h["version"], h["reason"], h["changed_by"]) for h in history(c, sid)] == [(1, "alta inicial", "buyer-1")]
        link = list_links(c, sid)
        assert len(link) == 1 and link[0]["sku"] == "SYN-000001"


def test_edits_and_status_changes_persist_and_earlier_versions_stay_readable(engine):
    with engine.begin() as c:
        sid = create_supplier(c, SupplierInput(name="Proveedor Sintetico Cambios", fiscal_type="national", country="ES", currency="EUR"), "buyer-1", now=NOW).id
        save_terms(c, sid, TERMS, "buyer-1", now=NOW)
    with engine.begin() as c:
        update_supplier(c, sid, {"payment_terms_days": 45}, "buyer-2", 1, now=NOW)
        save_terms(c, sid, Terms(**{**TERMS.__dict__, "lead_time_days": 5}), "buyer-2", now=NOW, expected_version=1)
        deactivate_supplier(c, sid, "buyer-2", confirm=True, now=NOW)
    with engine.begin() as c:
        row = get_supplier(c, sid)
        assert (row.status, row.payment_terms_days, row.version) == ("deactivated", 45, 3)
        assert [h["terms"].lead_time_days for h in history(c, sid)] == [3, 5]            # version 1 is untouched
        reactivate_supplier(c, sid, "buyer-2", now=NOW)
    with engine.begin() as c:
        assert get_supplier(c, sid).status == "active"
