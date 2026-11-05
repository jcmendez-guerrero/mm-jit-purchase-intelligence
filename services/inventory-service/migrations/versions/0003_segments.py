"""product segments, service levels, criticality audit, variant price.

Revision ID: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("variants", sa.Column("price", sa.Numeric(18, 6)))
    op.create_table("product_segments", sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("abc", sa.String(1), nullable=False), sa.Column("xyz", sa.String(1), nullable=False),
                    sa.Column("pattern", sa.String(14), nullable=False), sa.Column("forecast_eligible", sa.Boolean, nullable=False),
                    sa.Column("reason", sa.String(200), nullable=False), sa.Column("metrics", sa.JSON, nullable=False),
                    sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("run_id", sa.String(36), nullable=False))
    op.create_table("service_level_config", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("scope", sa.String(10), nullable=False), sa.Column("key", sa.String(20), nullable=False),
                    sa.Column("target", sa.Numeric(5, 4), nullable=False), sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("changed_by", sa.String(120), nullable=False))
    op.create_index("ix_service_level_lookup", "service_level_config", ["scope", "key", "valid_from"])
    op.create_table("criticality_changes", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                    sa.Column("product_id", sa.Integer, nullable=False), sa.Column("clinical_critical", sa.Boolean, nullable=False),
                    sa.Column("changed_by", sa.String(120), nullable=False), sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    for t in ("criticality_changes", "service_level_config", "product_segments"):
        op.drop_table(t)
    op.drop_column("variants", "price")
