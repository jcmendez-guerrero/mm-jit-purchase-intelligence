"""suppliers managed in the platform, review items, bulk-assignment batches and export cost references (MMI 004).

Existing rows come from the ERP, so they become purchasing suppliers with origin ``erp`` and a linked ERP contact.
Nothing here is written to the ERP. Tax ids, bank details and free-text notes are never stored.

Revision ID: 0011
"""

import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

SUPPLIER_COLUMNS = [
    "name_key", "status", "classification", "origin", "erp_link_state", "fiscal_type", "country", "currency", "payment_terms_days",
    "order_channel", "has_note", "version", "created_by", "created_at", "updated_by", "updated_at", "deactivated_by", "deactivated_at", "merged_into",
]


def _fold(text: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c))
    return " ".join("".join(ch for ch in stripped.lower() if ch not in ".,").split())


def _cost_source_check(values: tuple[str, ...]) -> None:
    """PostgreSQL only: the cost source list is a table CHECK (migration 0001); SQLite test databases never had it."""
    if op.get_bind().dialect.name != "postgresql":
        return
    op.drop_constraint("ck_cost_source", "supplier_costs", type_="check")
    op.create_check_constraint("ck_cost_source", "supplier_costs", "source in (" + ",".join(f"'{v}'" for v in values) + ")")


def upgrade() -> None:
    _cost_source_check(("siweb_product_supplier", "csv_price_list", "manual", "inventory_export"))
    with op.batch_alter_table("suppliers") as b:
        b.add_column(sa.Column("name_key", sa.String(200), nullable=False, server_default=""))
        b.add_column(sa.Column("status", sa.String(12), nullable=False, server_default="active"))
        b.add_column(sa.Column("classification", sa.String(16), nullable=False, server_default="unclassified"))
        b.add_column(sa.Column("origin", sa.String(10), nullable=False, server_default="platform"))
        b.add_column(sa.Column("erp_link_state", sa.String(12), nullable=False, server_default="none"))
        b.add_column(sa.Column("fiscal_type", sa.String(16), nullable=False, server_default="national"))
        b.add_column(sa.Column("country", sa.String(2), nullable=False, server_default="ES"))
        b.add_column(sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"))
        b.add_column(sa.Column("payment_terms_days", sa.Integer))
        b.add_column(sa.Column("order_channel", sa.String(8)))
        b.add_column(sa.Column("has_note", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("version", sa.Integer, nullable=False, server_default="1"))
        b.add_column(sa.Column("created_by", sa.String(120)))
        b.add_column(sa.Column("created_at", sa.DateTime(timezone=True)))
        b.add_column(sa.Column("updated_by", sa.String(120)))
        b.add_column(sa.Column("updated_at", sa.DateTime(timezone=True)))
        b.add_column(sa.Column("deactivated_by", sa.String(120)))
        b.add_column(sa.Column("deactivated_at", sa.DateTime(timezone=True)))
        b.add_column(sa.Column("merged_into", sa.String(36)))
    # rows that already exist were collected from the ERP
    bind = op.get_bind()
    for sid, name in bind.execute(sa.text("SELECT id, name FROM suppliers")).fetchall():
        bind.execute(
            sa.text("UPDATE suppliers SET name_key = :k, classification = 'purchasing', origin = 'erp', erp_link_state = 'linked' WHERE id = :i"),
            {"k": _fold(name), "i": sid},
        )
    op.create_index("ix_suppliers_name_key", "suppliers", ["name_key"])

    op.create_table(
        "supplier_review_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id")),
        sa.Column("detail", sa.String(200), nullable=False, server_default=""),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_by", sa.String(120)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "link_assignment_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_by", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("criteria", sa.JSON, nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("products_matched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("products_changed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("conflicts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(10), nullable=False, server_default="previewed"),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "export_costs",
        sa.Column("sku", sa.String(60), primary_key=True),
        sa.Column("export_cost", sa.Numeric(18, 4)),
        sa.Column("pvp_gross", sa.Numeric(18, 4)),
        sa.Column("tax_rate", sa.Numeric(5, 2)),
        sa.Column("tax_included", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("load_run_id", sa.String(36)),
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("UPDATE supplier_costs SET source = 'manual' WHERE source = 'inventory_export'")      # the old list cannot hold it
    _cost_source_check(("siweb_product_supplier", "csv_price_list", "manual"))
    op.drop_table("export_costs")
    op.drop_table("link_assignment_batches")
    op.drop_table("supplier_review_items")
    op.drop_index("ix_suppliers_name_key", table_name="suppliers")
    with op.batch_alter_table("suppliers") as b:
        for name in reversed(SUPPLIER_COLUMNS):
            b.drop_column(name)
