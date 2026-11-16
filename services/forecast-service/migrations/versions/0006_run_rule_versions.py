"""forecast runs record the exclusion and censoring-rule revisions they used (feature 011).

Nullable: runs made before this change, or from an inventory export without rule versions, keep NULL.

Revision ID: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("forecast_runs", sa.Column("rule_version_ids", sa.JSON, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("forecast_runs") as b:
        b.drop_column("rule_version_ids")
