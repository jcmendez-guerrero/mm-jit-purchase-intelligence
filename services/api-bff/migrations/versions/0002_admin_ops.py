"""administration and operations: alerts, alert observations, ops snapshots, ops settings (feature 010).

Revision ID: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("alerts", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
                    sa.Column("condition_key", sa.String(40), nullable=False), sa.Column("subject", sa.String(80), nullable=False),
                    sa.Column("severity", sa.String(10), nullable=False), sa.Column("state", sa.String(14), nullable=False, server_default="open"),
                    sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("acknowledged_by", sa.String(120)), sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
                    sa.Column("closed_at", sa.DateTime(timezone=True)), sa.Column("reason_code", sa.String(40), nullable=False))
    op.create_index("uq_alerts_live", "alerts", ["condition_key", "subject"], unique=True,
                    sqlite_where=sa.text("state <> 'closed'"), postgresql_where=sa.text("state <> 'closed'"))
    op.create_table("alert_observations", sa.Column("condition_key", sa.String(40), primary_key=True), sa.Column("subject", sa.String(80), primary_key=True),
                    sa.Column("count", sa.Integer, nullable=False, server_default="1"), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("ops_snapshots", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
                    sa.Column("kind", sa.String(10), nullable=False), sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("captured_at_original", sa.String(40), nullable=False), sa.Column("payload", sa.JSON, nullable=False),
                    sa.Column("status", sa.String(12), nullable=False))
    op.create_index("ix_ops_snapshots_kind", "ops_snapshots", ["kind", "captured_at"])
    op.create_table("ops_settings", sa.Column("key", sa.String(40), primary_key=True), sa.Column("value", sa.Integer, nullable=False),
                    sa.Column("updated_by", sa.String(120), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("alert_observations")
    op.drop_table("ops_settings")
    op.drop_index("ix_ops_snapshots_kind", table_name="ops_snapshots")
    op.drop_table("ops_snapshots")
    op.drop_index("uq_alerts_live", table_name="alerts")
    op.drop_table("alerts")
