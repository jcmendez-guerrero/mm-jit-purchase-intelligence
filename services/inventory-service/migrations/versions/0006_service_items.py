"""services (not physical stock) are flagged on the variant and excluded from stock, demand, forecasts and risks (MMI 004, FR-036).

Revision ID: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("variants", sa.Column("is_service", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("variants") as b:
        b.drop_column("is_service")
