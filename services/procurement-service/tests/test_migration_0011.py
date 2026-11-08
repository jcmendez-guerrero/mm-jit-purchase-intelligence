"""T021: migration 0011 matches the table definitions, backfills existing ERP suppliers, and downgrades cleanly (SQLite check)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from db.tables import export_costs, link_assignment_batches, supplier_review_items, suppliers

MIG = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0011_suppliers.py"
spec = importlib.util.spec_from_file_location("mig0011", MIG)
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)

OLD_COLUMNS = {"id", "external_contact_id", "name"}


def prepare() -> sa.engine.Engine:
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(sa.text("CREATE TABLE suppliers (id VARCHAR(36) PRIMARY KEY, external_contact_id INTEGER UNIQUE, name VARCHAR(200) NOT NULL)"))
        c.execute(sa.text("INSERT INTO suppliers (id, external_contact_id, name) VALUES ('a', 9001, 'Distribuciones Sintéticas, S.L.')"))
    return eng


def run(eng, fn):
    with eng.begin() as c:
        ctx = MigrationContext.configure(c)
        with Operations.context(ctx):
            fn()


def columns(eng, table):
    return {c["name"] for c in sa.inspect(eng).get_columns(table)}


def test_revision_chain():
    assert mig.revision == "0011" and mig.down_revision == "0010"


def test_upgrade_matches_table_definitions_and_backfills_existing_rows():
    eng = prepare()
    run(eng, mig.upgrade)
    assert columns(eng, "suppliers") == {c.name for c in suppliers.columns}
    assert columns(eng, "supplier_review_items") == {c.name for c in supplier_review_items.columns}
    assert columns(eng, "link_assignment_batches") == {c.name for c in link_assignment_batches.columns}
    assert columns(eng, "export_costs") == {c.name for c in export_costs.columns}
    with eng.connect() as c:
        row = c.execute(sa.text("SELECT name_key, classification, origin, erp_link_state, status, currency, has_note FROM suppliers")).one()
    assert tuple(row)[:6] == ("distribuciones sinteticas sl", "purchasing", "erp", "linked", "active", "EUR")
    assert not row[6]


def test_downgrade_restores_the_old_shape():
    eng = prepare()
    run(eng, mig.upgrade)
    run(eng, mig.downgrade)
    assert columns(eng, "suppliers") == OLD_COLUMNS
    assert not {"supplier_review_items", "link_assignment_batches", "export_costs"} & set(sa.inspect(eng).get_table_names())


def test_no_sensitive_columns_are_defined():
    banned = {"cif", "tax_id", "iban", "swift", "bank", "notes", "note", "billing_address"}
    assert not banned & {c.name for c in suppliers.columns}
    assert not banned & {c.name for c in supplier_review_items.columns}


def test_the_cost_source_check_is_extended_on_postgresql_only():
    """The live Docker test proves the PostgreSQL behaviour; here the SQLite path must stay a no-op and the new value must be in the statement."""
    text = MIG.read_text()
    assert "ck_cost_source" in text and "inventory_export" in text and 'dialect.name != "postgresql"' in text
