"""T045 (behavioural): saving and resolving terms never opens a network connection."""

import socket
from decimal import Decimal

import httpx
from conftest import NOW, add_supplier
from costs.recargo import load_table
from costs.rules import CostRules
from costs.store import NewCost, add_version
from db.tables import cost_write_requests, erp_supplier_links, lot_acquisition_costs, product_refs, supplier_costs
from sqlalchemy import insert, select
from suppliers.links import LinkInput, put_link
from suppliers.service import SupplierInput, create_supplier, deactivate_supplier, reactivate_supplier, update_supplier
from suppliers_support import make_ref
from terms.overrides import OverrideTerms, save_override
from terms.resolve import resolve_effective
from terms.service import Terms, save_terms
from test_terms_scenarios import plan, world

D = Decimal


def test_saving_and_resolving_terms_makes_no_http_or_socket_call(conn, monkeypatch):
    def tripwire(*a, **k):
        raise AssertionError("terms must stay local: a network call was attempted")

    monkeypatch.setattr(httpx.Client, "send", tripwire)
    monkeypatch.setattr(httpx.AsyncClient, "send", tripwire)
    monkeypatch.setattr(socket, "create_connection", tripwire)
    sid = add_supplier(conn, 1, "Proveedor Sintético A")
    save_terms(conn, sid, Terms(lead_time_days=3, preferred=True), "buyer-1", NOW)
    save_override(conn, 9001, sid, OverrideTerms(pack_multiple=6), "buyer-1", NOW)
    assert resolve_effective(conn, sid, 9001, NOW).pack_multiple == 6


# ---- MMI-6 T027 (FR-023, FR-024, FR-025, SC-006, SC-009) ----
def _no_network(monkeypatch):
    def tripwire(*a, **k):
        raise AssertionError("supplier maintenance and proposals must not reach the network")

    monkeypatch.setattr(httpx.Client, "send", tripwire)
    monkeypatch.setattr(httpx.AsyncClient, "send", tripwire)
    monkeypatch.setattr(socket, "create_connection", tripwire)


def _erp_owned(conn):
    """Everything the ERP owns that supplier maintenance must never change: catalogue refs, ERP links, ERP costs, lot costs and cost-write requests."""
    snapshot = {}
    for table in (product_refs, erp_supplier_links, lot_acquisition_costs, cost_write_requests):
        keys = list(table.primary_key.columns) or [next(iter(table.c))]
        snapshot[table.name] = [tuple(r) for r in conn.execute(select(table).order_by(*keys)).all()]
    erp = conn.execute(select(supplier_costs).where(supplier_costs.c.source == "siweb_product_supplier").order_by(supplier_costs.c.id)).all()
    snapshot["erp_costs"] = [tuple(r) for r in erp]
    return snapshot


def test_supplier_maintenance_changes_no_erp_owned_data_and_makes_no_network_call(conn, monkeypatch):
    make_ref(conn, 1, 10, "SYN-000001")
    erp_supplier = add_supplier(conn, 77, "Proveedor Sintético ERP")
    add_version(conn, NewCost(product_id=10, supplier_id=erp_supplier, cost_with_recargo=D("2.00"), source="siweb_product_supplier", actor="siweb-import"), CostRules(), NOW)
    conn.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=erp_supplier, has_cost=True, last_seen_at=NOW))
    before = _erp_owned(conn)
    assert before["erp_costs"] and before["product_refs"] and before["erp_supplier_links"]       # the snapshot really has something to protect
    _no_network(monkeypatch)

    local = create_supplier(conn, SupplierInput(name="Proveedor Sintético Local", fiscal_type="national", country="ES", currency="EUR"), "buyer-1", now=NOW).id
    update_supplier(conn, local, {"payment_terms_days": 30}, "buyer-1", 1, now=NOW)
    save_terms(conn, local, Terms(lead_time_days=3, order_days=(1, 4), delivery_weekdays=(2, 5)), "buyer-1", NOW)
    save_terms(conn, erp_supplier, Terms(lead_time_days=2, preferred=True), "buyer-1", NOW)          # terms for an ERP supplier stay local too
    save_override(conn, 1, erp_supplier, OverrideTerms(pack_multiple=6), "buyer-1", NOW)
    put_link(conn, local, "SYN-000001", LinkInput(cost=D("1.80"), includes_recargo=False), "buyer-1", CostRules(), load_table(conn), now=NOW)
    deactivate_supplier(conn, local, "buyer-1", confirm=True, now=NOW)
    reactivate_supplier(conn, local, "buyer-1", now=NOW)

    assert _erp_owned(conn) == before


def test_a_supplier_created_here_has_no_erp_request_and_still_drives_proposals(conn, monkeypatch):
    sa, _sb = world(conn)
    local = create_supplier(conn, SupplierInput(name="Proveedor Sintético Local", fiscal_type="national", country="ES", currency="EUR"), "buyer-1", now=NOW)
    assert local.erp_link_state == "none" and local.external_contact_id is None                    # "pending link in ERP": nothing was sent
    _no_network(monkeypatch)
    save_terms(conn, sa, Terms(lead_time_days=2), "buyer-1", NOW)
    assert plan(conn)[2].explanation["terms"]["supplier_version"] == 1


def test_proposal_generation_from_local_data_needs_no_network(conn, monkeypatch):
    world(conn)
    _no_network(monkeypatch)
    built, draft, line = plan(conn)
    assert draft.lines and line.qty > 0 and built.suppliers
