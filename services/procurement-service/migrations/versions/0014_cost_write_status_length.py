"""cost_write_requests.status holds up to 24 characters (feature 011, found by running the suite on PostgreSQL).

``approved_by_buyer`` is 17 characters and the column held 16: SQLite does not check the length, PostgreSQL refuses the update, so a buyer's
approval of a supplier-cost write failed on a real database. Widening a column is additive; the downgrade narrows it back and stops if a
longer value is stored.

Revision ID: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cost_write_requests") as b:
        b.alter_column("status", existing_type=sa.String(16), type_=sa.String(24), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("cost_write_requests") as b:
        b.alter_column("status", existing_type=sa.String(24), type_=sa.String(16), existing_nullable=False)
