"""user roles mirror, forecast runs seen, receipt cursor.

Revision ID: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("user_roles", sa.Column("user_id", sa.String(120), primary_key=True), sa.Column("roles", sa.JSON, nullable=False),
                    sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()), sa.Column("updated_by", sa.String(120), nullable=False),
                    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("forecast_runs_seen", sa.Column("run_id", sa.String(36), primary_key=True), sa.Column("input_hash", sa.String(64), nullable=False),
                    sa.Column("eligible_count", sa.Integer, nullable=False), sa.Column("received_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("receipt_cursor", sa.Column("id", sa.Integer, primary_key=True, autoincrement=False), sa.Column("last_movement_id", sa.BigInteger, nullable=False))


def downgrade() -> None:
    for t in ("receipt_cursor", "forecast_runs_seen", "user_roles"):
        op.drop_table(t)
