"""discount applied to a supplier order group (MMI 002, FR-014).

Revision ID: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("supplier_order_groups", sa.Column("discount", sa.Numeric(18, 4), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("supplier_order_groups", "discount")
