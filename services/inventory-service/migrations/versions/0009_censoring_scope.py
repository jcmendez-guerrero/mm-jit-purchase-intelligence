"""censoring rules apply by scope: global, segment or product (feature 011).

Existing rows are global rules and keep working: the new columns default to scope 'global' and key '*'.

Revision ID: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("censoring_rules", sa.Column("scope", sa.String(10), nullable=False, server_default="global"))
    op.add_column("censoring_rules", sa.Column("key", sa.String(40), nullable=False, server_default="*"))


def downgrade() -> None:
    with op.batch_alter_table("censoring_rules") as b:
        b.drop_column("key")
        b.drop_column("scope")
