"""revision on the mirrored user roles, so a retried older change from the BFF never overwrites a newer one (MMI 002, FR-001).

Revision ID: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_roles", sa.Column("revision", sa.Integer, nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("user_roles", "revision")
