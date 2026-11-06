"""effective-dated supplier terms and product-supplier overrides (MMI 002, ADR-019). Nothing here is written to the ERP.

Revision ID: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

NEW_COLUMNS = [
    sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    sa.Column("valid_to", sa.DateTime(timezone=True)),
    sa.Column("lead_time_days", sa.Integer),
    sa.Column("order_cutoff_time", sa.String(5)),
    sa.Column("delivery_weekdays", sa.JSON),
    sa.Column("discounts", sa.JSON),
    sa.Column("payment_terms_days", sa.Integer),
    sa.Column("preferred", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("reliability", sa.Integer),
    sa.Column("disabled", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("source", sa.String(10), nullable=False, server_default="manual"),
    sa.Column("reason", sa.String(500)),
    sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
]


def upgrade() -> None:
    for col in NEW_COLUMNS:
        op.add_column("supplier_terms", col)
    # number the existing versions per supplier in the order they were saved
    op.execute("""UPDATE supplier_terms SET version = (SELECT COUNT(*) FROM supplier_terms t2 WHERE t2.supplier_id = supplier_terms.supplier_id
                  AND (t2.valid_from < supplier_terms.valid_from OR (t2.valid_from = supplier_terms.valid_from AND t2.id <= supplier_terms.id)))""")
    op.create_table(
        "product_supplier_terms", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("variant_id", sa.Integer, nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False), sa.Column("version", sa.Integer, nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False), sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("lead_time_days", sa.Integer), sa.Column("order_days", sa.JSON), sa.Column("order_cutoff_time", sa.String(5)), sa.Column("delivery_weekdays", sa.JSON),
        sa.Column("min_order_value", sa.Numeric(18, 4)), sa.Column("min_qty_for_delivery", sa.Integer), sa.Column("free_delivery_threshold", sa.Numeric(18, 4)),
        sa.Column("delivery_charge", sa.Numeric(18, 4)), sa.Column("discounts", sa.JSON), sa.Column("payment_terms_days", sa.Integer),
        sa.Column("preferred", sa.Boolean), sa.Column("reliability", sa.Integer), sa.Column("disabled", sa.Boolean),
        sa.Column("pack_multiple", sa.Integer), sa.Column("min_qty_units", sa.Integer), sa.Column("source", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(500)), sa.Column("changed_by", sa.String(120), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("variant_id", "supplier_id", "version", name="uq_product_supplier_terms_version"),
    )


def downgrade() -> None:
    op.drop_table("product_supplier_terms")
    for col in reversed(NEW_COLUMNS):
        op.drop_column("supplier_terms", col.name)
