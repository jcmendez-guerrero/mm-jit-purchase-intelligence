"""T040 (FR-012 to FR-018, FR-021): create, edit, classify, deactivate and reactivate suppliers; duplicates are warned about, never merged."""

import pytest
from audit.chain import verify_chain
from conftest import NOW, add_supplier
from db.tables import audit_events, supplier_review_items, suppliers
from sqlalchemy import select
from suppliers.dedupe import name_key
from suppliers.service import (
    SupplierConflict,
    SupplierError,
    SupplierInput,
    create_supplier,
    deactivate_supplier,
    deactivation_preview,
    list_suppliers,
    reactivate_supplier,
    update_supplier,
)
from suppliers_support import open_line


def data(**kw):
    base = {"name": "Proveedor Sintetico Uno S.L.", "fiscal_type": "national", "country": "ES", "currency": "EUR"}
    base.update(kw)
    return SupplierInput(**base)


def audits(conn, action):
    return [r for r in conn.execute(select(audit_events)).all() if r.action == action]


def test_name_key_ignores_case_accents_punctuation_and_spacing():
    assert name_key("  Distribuciones   Sintéticas, S.L. ") == name_key("DISTRIBUCIONES SINTETICAS SL")


def test_create_sets_platform_defaults_and_audits(conn):
    s = create_supplier(conn, data(payment_terms_days=30, order_channel="email"), "buyer-1", now=NOW)
    assert (s.origin, s.status, s.classification, s.erp_link_state, s.version, s.external_contact_id) == ("platform", "active", "purchasing", "none", 1, None)
    assert s.name_key == name_key(s.name) and s.payment_terms_days == 30 and s.has_note is False and s.created_by == "buyer-1"
    assert len(audits(conn, "supplier.created")) == 1
    assert verify_chain(conn).ok


def test_a_duplicate_name_is_refused_until_confirmed_and_then_listed_for_review(conn):
    first = create_supplier(conn, data(), "buyer-1", now=NOW)
    with pytest.raises(SupplierError) as exc:
        create_supplier(conn, data(name="PROVEEDOR SINTÉTICO UNO SL"), "buyer-1", now=NOW)
    assert exc.value.code == "supplier_possible_duplicate" and exc.value.duplicates == [first.id]
    second = create_supplier(conn, data(name="PROVEEDOR SINTÉTICO UNO SL"), "buyer-1", confirm_duplicate=True, now=NOW)
    assert second.id != first.id
    items = conn.execute(select(supplier_review_items)).all()
    assert [(i.kind, i.supplier_id, i.status) for i in items] == [("possible_duplicate", second.id, "open")]
    assert "Proveedor" not in items[0].detail          # no names in review details


@pytest.mark.parametrize("field,value", [("name", "  "), ("name", "x" * 201), ("fiscal_type", "other"), ("country", "ESP"), ("country", "es"), ("currency", "euro"),
                                          ("payment_terms_days", -1), ("payment_terms_days", 400), ("order_channel", "fax"), ("classification", "maybe")])
def test_invalid_values_are_refused(conn, field, value):
    with pytest.raises(SupplierError) as exc:
        create_supplier(conn, data(**{field: value}), "buyer-1", now=NOW)
    assert exc.value.code == "supplier_invalid" and exc.value.field == field


def test_the_input_has_no_place_for_tax_id_bank_or_notes():
    banned = {"cif", "tax_id", "iban", "swift", "bank", "notes", "note", "billing_address"}
    assert not banned & set(SupplierInput.__dataclass_fields__)
    with pytest.raises(TypeError):
        SupplierInput(name="x", fiscal_type="national", country="ES", currency="EUR", cif="X1")  # type: ignore[call-arg]


def test_update_needs_the_version_and_bumps_it(conn):
    s = create_supplier(conn, data(), "buyer-1", now=NOW)
    updated = update_supplier(conn, s.id, {"payment_terms_days": 45, "currency": "EUR", "order_channel": "web"}, "buyer-2", s.version, now=NOW)
    assert (updated.version, updated.payment_terms_days, updated.order_channel, updated.updated_by) == (2, 45, "web", "buyer-2")
    assert audits(conn, "supplier.updated")
    with pytest.raises(SupplierConflict) as exc:
        update_supplier(conn, s.id, {"payment_terms_days": 10}, "buyer-2", 1, now=NOW)
    assert exc.value.current_version == 2


def test_renaming_re_checks_duplicates(conn):
    create_supplier(conn, data(name="Proveedor Alfa"), "buyer-1", now=NOW)
    b = create_supplier(conn, data(name="Proveedor Beta"), "buyer-1", now=NOW)
    with pytest.raises(SupplierError) as exc:
        update_supplier(conn, b.id, {"name": "proveedor alfa"}, "buyer-1", b.version, now=NOW)
    assert exc.value.code == "supplier_possible_duplicate"


def test_classification_can_change_both_ways(conn):
    s = create_supplier(conn, data(), "buyer-1", now=NOW)
    s = update_supplier(conn, s.id, {"classification": "non_purchasing"}, "buyer-1", s.version, now=NOW)
    assert s.classification == "non_purchasing"
    s = update_supplier(conn, s.id, {"classification": "purchasing"}, "buyer-1", s.version, now=NOW)
    assert s.classification == "purchasing"
    with pytest.raises(SupplierError):
        update_supplier(conn, s.id, {"classification": "weird"}, "buyer-1", s.version, now=NOW)


def test_unknown_suppliers_give_a_stable_code(conn):
    with pytest.raises(SupplierError) as exc:
        update_supplier(conn, "nope", {"name": "x"}, "buyer-1", 1, now=NOW)
    assert exc.value.code == "supplier_not_found"


def test_deactivation_previews_the_open_lines_and_changes_nothing(conn):
    s = create_supplier(conn, data(), "buyer-1", now=NOW)
    open_line(conn, s.id, 1, "draft")
    open_line(conn, s.id, 2, "submitted")
    open_line(conn, s.id, 3, "exported")
    preview = deactivate_supplier(conn, s.id, "buyer-1", confirm=False, now=NOW)
    assert preview["deactivated"] is False and preview["open_proposal_lines"] == 2
    assert conn.execute(select(suppliers.c.status).where(suppliers.c.id == s.id)).scalar() == "active"


def test_confirmed_deactivation_keeps_history_and_flags_the_proposals(conn):
    s = create_supplier(conn, data(), "buyer-1", now=NOW)
    pid = open_line(conn, s.id, 1, "draft")
    out = deactivate_supplier(conn, s.id, "admin-1", confirm=True, now=NOW)
    row = conn.execute(select(suppliers).where(suppliers.c.id == s.id)).one()
    assert out["deactivated"] is True and row.status == "deactivated" and (row.deactivated_by, row.version) == ("admin-1", 2) and row.name == s.name
    items = conn.execute(select(supplier_review_items)).all()
    assert [(i.kind, i.supplier_id, i.status) for i in items] == [("proposal_reallocation", s.id, "open")] and pid
    assert audits(conn, "supplier.deactivated")


def test_a_deactivated_supplier_cannot_be_edited_until_reactivated(conn):
    s = create_supplier(conn, data(), "buyer-1", now=NOW)
    deactivate_supplier(conn, s.id, "buyer-1", confirm=True, now=NOW)
    cur = conn.execute(select(suppliers.c.version).where(suppliers.c.id == s.id)).scalar()
    with pytest.raises(SupplierError) as exc:
        update_supplier(conn, s.id, {"payment_terms_days": 5}, "buyer-1", cur, now=NOW)
    assert exc.value.code == "supplier_deactivated"
    back = reactivate_supplier(conn, s.id, "buyer-1", now=NOW)
    assert back.status == "active" and back.deactivated_at is None and audits(conn, "supplier.reactivated")


def test_deactivation_preview_function_counts_only_open_proposals(conn):
    s = create_supplier(conn, data(), "buyer-1", now=NOW)
    open_line(conn, s.id, 1, "approved")
    open_line(conn, s.id, 2, "superseded")
    assert deactivation_preview(conn, s.id)["open_proposal_lines"] == 1


def test_list_filters_by_status_classification_and_text(conn):
    a = create_supplier(conn, data(name="Alfa Sintetica"), "b", now=NOW)
    create_supplier(conn, data(name="Beta Sintetica", classification="non_purchasing"), "b", now=NOW)
    deactivate_supplier(conn, a.id, "b", confirm=True, now=NOW)
    add_supplier(conn, 77, "Gamma ERP")
    names = lambda **f: [s.name for s in list_suppliers(conn, **f)]  # noqa: E731
    assert names(status="active") == ["Beta Sintetica", "Gamma ERP"] or set(names(status="active")) == {"Beta Sintetica", "Gamma ERP"}
    assert names(classification="non_purchasing") == ["Beta Sintetica"]
    assert names(q="alf") == ["Alfa Sintetica"]
    assert names(q="ALFA") == ["Alfa Sintetica"]
