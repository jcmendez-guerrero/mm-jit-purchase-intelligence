"""demand exclusions keep a pick-list reason and a short admin-only detail (feature 011).

The reason column now holds a pick-list code; the free-text detail moves to its own short column so it can be shown to admins only and
never reaches the audit trail. Older rows are left as they are.

Revision ID: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("demand_exclusions", sa.Column("reason_detail", sa.String(100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("demand_exclusions") as b:
        b.drop_column("reason_detail")
