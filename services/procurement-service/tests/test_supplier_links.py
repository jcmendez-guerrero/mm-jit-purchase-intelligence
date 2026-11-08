"""T041 (FR-015, FR-016, FR-040): product-supplier links by SKU, with the existing cost provenance; no ERP request is ever made from here."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from conftest import NOW, add_supplier
from costs.recargo import load_table
from costs.rules import CostRules
from db.tables import cost_write_requests, erp_supplier_links, export_costs, supplier_costs, suppliers
from sqlalchemy import insert, select, update
from suppliers.links import LinkError, LinkInput, list_links, put_link, remove_link
from suppliers.service import SupplierInput, create_supplier, deactivate_supplier
from suppliers_support import make_ref

D = Decimal


def supplier(conn, **kw):
    base = {"name": "Proveedor Sintetico", "fiscal_type": "national", "country": "ES", "currency": "EUR"}
    base.update(kw)
    return create_supplier(conn, SupplierInput(**base), "buyer-1", now=NOW)


def put(conn, sid, sku, **kw):
    return put_link(conn, sid, sku, LinkInput(**kw), "buyer-1", CostRules(), load_table(conn), now=NOW)


def costs_of(conn, sid):
    return list(conn.execute(select(supplier_costs).where(supplier_costs.c.supplier_id == sid).order_by(supplier_costs.c.version)).all())


def test_a_net_cost_is_shown_with_recargo_and_keeps_its_provenance(conn):
    make_ref(conn, 1, 10, "SYN-000001", vat=D("21"))
    s = supplier(conn)
    r = put(conn, s.id, "SYN-000001", cost=D("100.00"), includes_recargo=False)
    c = r.cost
    assert (c.cost_net, c.cost_with_recargo, c.source, c.verified_by, c.entered_includes_recargo) == (D("100.0000"), D("105.2000"), "manual", "buyer-1", False)
    assert r.erp_link == "no_link" and r.write_case == "pending_link"


def test_a_cost_that_already_includes_recargo_is_kept_as_entered(conn):
    make_ref(conn, 1, 10, "SYN-000001", vat=D("10"))
    s = supplier(conn)
    assert put(conn, s.id, "SYN-000001", cost=D("7.50"), includes_recargo=True).cost.cost_with_recargo == D("7.5000")


def test_pack_and_minimum_quantity_travel_with_the_cost(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    c = put(conn, s.id, "SYN-000001", cost=D("2.00"), pack_size=6, min_qty=12).cost
    assert (c.pack_size, c.min_order_qty) == (6, 12)


def test_the_export_cost_is_the_default_and_its_source_is_inventory_export(conn):
    make_ref(conn, 1, 10, "SYN-000001", vat=None)
    conn.execute(insert(export_costs).values(sku="SYN-000001", export_cost=D("10.00"), pvp_gross=D("15.00"), tax_rate=D("21"), tax_included=False, currency="EUR", loaded_at=NOW))
    s = supplier(conn)
    r = put(conn, s.id, "SYN-000001", source="inventory_export")
    assert (r.cost.source, r.cost.cost_net, r.cost.cost_with_recargo, r.cost.vat_rate_used) == ("inventory_export", D("10.0000"), D("10.5200"), D("21.00"))


def test_without_any_cost_the_link_is_refused(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    with pytest.raises(LinkError) as exc:
        put(conn, s.id, "SYN-000001")
    assert exc.value.code == "link_cost_invalid"
    with pytest.raises(LinkError):
        put(conn, s.id, "SYN-000001", cost=D("-1"))


def test_unknown_sku_is_refused_and_the_refresh_hook_gets_one_chance(conn):
    s = supplier(conn)
    with pytest.raises(LinkError) as exc:
        put(conn, s.id, "SYN-404", cost=D("1"))
    assert exc.value.code == "link_sku_unknown"
    calls = []

    def refresh():
        calls.append(1)
        make_ref(conn, 5, 50, "SYN-000005")

    r = put_link(conn, s.id, "syn-000005", LinkInput(cost=D("1.00")), "buyer-1", CostRules(), load_table(conn), now=NOW, refresh=refresh)
    assert calls == [1] and r.cost.product_id == 50


def test_sku_matching_ignores_case_and_spaces(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    assert put(conn, s.id, "  syn-000001 ", cost=D("1.00")).cost.product_id == 10


def test_a_supplier_without_an_erp_counterpart_is_pending_link_and_no_erp_request_exists(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    r = put(conn, s.id, "SYN-000001", cost=D("1.00"))
    assert (r.erp_link, r.write_case) == ("no_link", "pending_link")
    assert conn.execute(select(cost_write_requests)).all() == []


def test_an_erp_supplier_without_a_cost_in_the_erp_is_a_missing_cost_case(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    sid = add_supplier(conn, 99, "ERP")
    conn.execute(insert(erp_supplier_links).values(product_id=10, supplier_id=sid, has_cost=False, last_seen_at=datetime.now(UTC)))
    r = put(conn, sid, "SYN-000001", cost=D("1.00"))
    assert (r.erp_link, r.write_case) == ("link_without_cost", "missing_cost")
    assert conn.execute(select(cost_write_requests)).all() == []          # the link screen never creates ERP writes


def test_a_foreign_currency_supplier_is_refused_for_eur_costs(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn, currency="USD")
    with pytest.raises(LinkError) as exc:
        put(conn, s.id, "SYN-000001", cost=D("1.00"))
    assert exc.value.code == "link_currency_mismatch"


def test_a_deactivated_supplier_cannot_get_new_links(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    deactivate_supplier(conn, s.id, "b", confirm=True, now=NOW)
    with pytest.raises(LinkError) as exc:
        put(conn, s.id, "SYN-000001", cost=D("1.00"))
    assert exc.value.code == "supplier_deactivated"


def test_updating_a_link_adds_a_version_and_flags_an_abnormal_jump(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    put(conn, s.id, "SYN-000001", cost=D("1.00"))
    r = put(conn, s.id, "SYN-000001", cost=D("5.00"))
    assert [c.version for c in costs_of(conn, s.id)] == [1, 2] and "abnormal_jump" in r.warnings


def test_removing_a_link_keeps_the_history(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    put(conn, s.id, "SYN-000001", cost=D("1.00"))
    remove_link(conn, s.id, "SYN-000001", "buyer-1", now=NOW)
    assert list_links(conn, s.id) == [] and len(costs_of(conn, s.id)) == 1
    with pytest.raises(LinkError) as exc:
        remove_link(conn, s.id, "SYN-000001", "buyer-1", now=NOW)
    assert exc.value.code == "link_not_found"


def test_listing_shows_sku_cost_source_and_verification(conn):
    make_ref(conn, 1, 10, "SYN-000001", name="Pienso sintético")
    s = supplier(conn)
    put(conn, s.id, "SYN-000001", cost=D("2.00"), pack_size=6)
    row = list_links(conn, s.id)[0]
    assert (row["sku"], row["name"], row["cost"], row["cost_source"], row["pack_size"]) == ("SYN-000001", "Pienso sintético", "2.0000", "manual", 6)
    assert row["verified_at"] and row["erp_link"] == "no_link"


def test_the_supplier_row_is_untouched_by_links(conn):
    make_ref(conn, 1, 10, "SYN-000001")
    s = supplier(conn)
    put(conn, s.id, "SYN-000001", cost=D("1.00"))
    assert conn.execute(select(suppliers.c.version).where(suppliers.c.id == s.id)).scalar() == 1
    assert conn.execute(update(suppliers).where(suppliers.c.id == s.id).values(version=1)).rowcount == 1
