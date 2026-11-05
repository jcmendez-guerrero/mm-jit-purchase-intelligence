"""inbound order projection (from procurement.order.confirmed.v1).

Revision ID: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("inbound_lines", sa.Column("order_id", sa.String(36), primary_key=True), sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("proposal_id", sa.String(36), nullable=False), sa.Column("supplier_id", sa.String(36), nullable=False),
                    sa.Column("qty", sa.Integer, nullable=False), sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("inbound_lines")
