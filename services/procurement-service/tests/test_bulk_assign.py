"""T042 (FR-035): bulk assignment of products to a supplier: preview first, conflicts shown, stale previews refused, per-product audit."""

from datetime import timedelta
from decimal import Decimal

import pytest
from conftest import NOW, add_supplier
from costs.recargo import load_table
from costs.rules import CostRules
from db.tables import audit_events, export_costs, link_assignment_batches, supplier_costs
from sqlalchemy import insert, select
from suppliers.bulk import BulkError, apply_batch, parse_assignment_file, preview_batch
from suppliers.service import SupplierInput, create_supplier
from suppliers_support import make_ref
from terms.overrides import OverrideTerms, save_override

D = Decimal


def supplier(conn, name="Proveedor Sintetico"):
    return create_supplier(conn, SupplierInput(name=name, fiscal_type="national", country="ES", currency="EUR"), "buyer-1", now=NOW)


def catalogue(conn, n=4):
    for i in range(1, n + 1):
        make_ref(conn, i, 100 + i, f"SYN-{i:06d}", name=f"Pienso Sintetico {i}", vat=D("21"))
        conn.execute(insert(export_costs).values(sku=f"SYN-{i:06d}", export_cost=D("2.00"), pvp_gross=D("4.00"), tax_rate=D("21"), tax_included=False,
                                                 currency="EUR", loaded_at=NOW))


def preview(conn, sid, criteria, now=NOW):
    return preview_batch(conn, sid, criteria, "buyer-1", now=now)


def apply(conn, batch, **kw):
    return apply_batch(conn, batch["batch_id"], "buyer-1", CostRules(), load_table(conn), now=kw.pop("now", NOW), **kw)


def test_preview_by_selection_counts_everything_and_changes_nothing(conn):
    catalogue(conn)
    s = supplier(conn)
    p = preview(conn, s.id, {"skus": ["SYN-000001", "syn-000002", "SYN-999999", "SYN-000002"]})
    assert (p["matched"], p["new"], p["existing"], p["conflicts"], p["unknown"]) == (2, 2, 0, 0, ["SYN-999999"])
    assert conn.execute(select(supplier_costs)).all() == []
    assert conn.execute(select(link_assignment_batches.c.status)).scalar() == "previewed"


def test_preview_by_free_text_matches_sku_and_name(conn):
    catalogue(conn)
    s = supplier(conn)
    assert preview(conn, s.id, {"q": "pienso sintetico 3"})["matched"] == 1
    assert preview(conn, s.id, {"q": "SYN-00000"})["matched"] == 4
    assert preview(conn, s.id, {"q": "nada"})["matched"] == 0


def test_an_empty_or_too_broad_request_is_refused(conn):
    catalogue(conn)
    s = supplier(conn)
    for bad in ({}, {"q": ""}, {"skus": []}):
        with pytest.raises(BulkError) as exc:
            preview(conn, s.id, bad)
        assert exc.value.code == "bulk_criteria_invalid"


def test_apply_creates_links_with_the_export_cost_and_audits_each_product(conn):
    catalogue(conn)
    s = supplier(conn)
    b = preview(conn, s.id, {"skus": ["SYN-000001", "SYN-000002"]})
    out = apply(conn, b)
    rows = list(conn.execute(select(supplier_costs)).all())
    assert totals(out) == {"changed": 2, "skipped_conflicts": 0, "no_cost": 0} and {r.source for r in rows} == {"inventory_export"}
    assert {r.cost_with_recargo for r in rows} == {D("2.1040")}
    per_product = [a for a in conn.execute(select(audit_events)).all() if a.action == "supplier.link_bulk"]
    assert len(per_product) == 2
    assert conn.execute(select(link_assignment_batches.c.status)).scalar() == "applied"


def test_products_that_already_have_a_link_are_counted_and_kept(conn):
    catalogue(conn)
    s = supplier(conn)
    apply(conn, preview(conn, s.id, {"skus": ["SYN-000001"]}))
    p = preview(conn, s.id, {"skus": ["SYN-000001", "SYN-000002"]})
    assert (p["new"], p["existing"]) == (1, 1)
    assert apply(conn, p)["changed"] == 1 and len(conn.execute(select(supplier_costs)).all()) == 2


def test_a_preferred_other_supplier_is_a_conflict_that_must_be_skipped_explicitly(conn):
    catalogue(conn)
    other = add_supplier(conn, 55, "Otro")
    save_override(conn, 1, other, OverrideTerms(preferred=True), "buyer-1", NOW, expected_version=0)
    s = supplier(conn)
    p = preview(conn, s.id, {"skus": ["SYN-000001", "SYN-000002"]})
    assert p["conflicts"] == 1 and p["conflict_skus"] == ["SYN-000001"]
    with pytest.raises(BulkError) as exc:
        apply(conn, p)
    assert exc.value.code == "bulk_conflicts_unresolved"
    out = apply(conn, p, skip_conflicts=True)
    assert out["changed"] == 1 and out["skipped_conflicts"] == 1


def outcomes(out):
    return {r["sku"]: r["outcome"] for r in out["rows"]}


def totals(out):
    """The three counters of an apply result, without the per-row list."""
    return {k: out[k] for k in ("changed", "skipped_conflicts", "no_cost")}


def test_apply_reports_an_outcome_for_every_matched_product(conn):
    """FR-018: the buyer sees what happened to each row, not only totals."""
    from costs.rules import CostRules as Rules
    from suppliers.links import LinkInput, put_link

    catalogue(conn, 4)
    conn.execute(export_costs.delete().where(export_costs.c.sku == "SYN-000004"))                 # no usable cost
    other = add_supplier(conn, 55, "Otro")
    save_override(conn, 3, other, OverrideTerms(preferred=True), "buyer-1", NOW, expected_version=0)   # SYN-000003 prefers another supplier
    s = supplier(conn)
    put_link(conn, s.id, "SYN-000001", LinkInput(source="inventory_export"), "buyer-1", Rules(), load_table(conn), now=NOW)   # already linked
    out = apply(conn, preview(conn, s.id, {"skus": ["SYN-000001", "SYN-000002", "SYN-000003", "SYN-000004"]}), skip_conflicts=True)
    assert outcomes(out) == {"SYN-000001": "already_linked", "SYN-000002": "linked", "SYN-000003": "conflict_skipped", "SYN-000004": "no_cost"}
    assert (out["changed"], out["skipped_conflicts"], out["no_cost"]) == (1, 1, 1)                 # the totals still agree with the rows


def test_the_rows_are_in_sku_order_and_list_each_product_once(conn):
    catalogue(conn, 3)
    s = supplier(conn)
    out = apply(conn, preview(conn, s.id, {"skus": ["SYN-000003", "SYN-000001", "syn-000001", "SYN-000002"]}))
    assert [r["sku"] for r in out["rows"]] == ["SYN-000001", "SYN-000002", "SYN-000003"]


def test_products_without_any_usable_cost_are_skipped_and_counted(conn):
    catalogue(conn, 2)
    conn.execute(export_costs.delete().where(export_costs.c.sku == "SYN-000002"))
    s = supplier(conn)
    out = apply(conn, preview(conn, s.id, {"skus": ["SYN-000001", "SYN-000002"]}))
    assert totals(out) == {"changed": 1, "skipped_conflicts": 0, "no_cost": 1}


def test_a_stale_or_superseded_preview_cannot_be_applied(conn):
    catalogue(conn)
    s = supplier(conn)
    old = preview(conn, s.id, {"skus": ["SYN-000001"]})
    with pytest.raises(BulkError) as exc:
        apply(conn, old, now=NOW + timedelta(minutes=16))
    assert exc.value.code == "bulk_preview_stale"
    first = preview(conn, s.id, {"skus": ["SYN-000001"]})
    preview(conn, s.id, {"skus": ["SYN-000002"]})
    with pytest.raises(BulkError) as exc:
        apply(conn, first)
    assert exc.value.code == "bulk_preview_stale"


def test_a_batch_applies_only_once(conn):
    catalogue(conn)
    s = supplier(conn)
    b = preview(conn, s.id, {"skus": ["SYN-000001"]})
    apply(conn, b)
    with pytest.raises(BulkError) as exc:
        apply(conn, b)
    assert exc.value.code == "bulk_preview_stale"


def test_the_stored_criteria_hold_no_personal_data_and_no_cost_values(conn):
    catalogue(conn)
    s = supplier(conn)
    preview(conn, s.id, {"skus": ["SYN-000001"]})
    stored = conn.execute(select(link_assignment_batches.c.criteria)).scalar()
    assert set(stored) == {"skus"}


def test_the_assignment_file_is_grouped_by_the_matching_supplier(conn):
    a, b = supplier(conn, "Proveedor Alfa S.L."), supplier(conn, "Proveedor Beta")
    add_supplier(conn, 71, "Repetido")
    add_supplier(conn, 72, "REPETIDO")
    csv_bytes = ("SKU;Proveedor\nSYN-000001;proveedor alfa sl\nSYN-000002;Proveedor Alfa S.L.\nSYN-000003;PROVEEDOR BETA\n"
                 "SYN-000004;Nadie\nSYN-000005;Repetido\n;Proveedor Beta\n").encode("utf-8-sig")
    out = parse_assignment_file(conn, csv_bytes)
    assert out["groups"] == {a.id: ["SYN-000001", "SYN-000002"], b.id: ["SYN-000003"]}
    codes = sorted((e["code"], e["row"]) for e in out["errors"])
    assert codes == [("link_no_match", 5), ("link_ambiguous", 6), ("missing_sku", 7)] or {c for c, _ in codes} == {"link_no_match", "link_ambiguous", "missing_sku"}
