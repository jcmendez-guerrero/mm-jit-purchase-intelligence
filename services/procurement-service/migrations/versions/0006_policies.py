"""purchase policy sets, budget caps, always-stocked settings and safety-stock override requests (MMI 002).

Revision ID: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("policy_sets", sa.Column("id", sa.String(36), primary_key=True), sa.Column("scope", sa.String(10), nullable=False),
                    sa.Column("key", sa.String(40), nullable=False), sa.Column("service_level", sa.Numeric(5, 4)), sa.Column("safety_stock_units", sa.Integer),
                    sa.Column("min_units", sa.Integer), sa.Column("max_units", sa.Integer), sa.Column("replenishment_cadence_days", sa.Integer),
                    sa.Column("valid_from", sa.Date, nullable=False), sa.Column("valid_to", sa.Date),
                    sa.Column("revision", sa.Integer, nullable=False, server_default="1"), sa.Column("changed_by", sa.String(120), nullable=False),
                    sa.UniqueConstraint("scope", "key", "valid_from", "revision", name="uq_policy_sets_effective"))
    op.create_table("budget_caps", sa.Column("id", sa.String(36), primary_key=True), sa.Column("period", sa.String(5), nullable=False),
                    sa.Column("scope", sa.String(10), nullable=False), sa.Column("scope_key", sa.String(40)), sa.Column("amount", sa.Numeric(18, 4), nullable=False),
                    sa.Column("valid_from", sa.Date, nullable=False), sa.Column("valid_to", sa.Date),
                    sa.Column("revision", sa.Integer, nullable=False, server_default="1"), sa.Column("changed_by", sa.String(120), nullable=False))
    op.create_table("stocking_settings", sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("stocking_mode", sa.String(14), nullable=False, server_default="standard"),
                    sa.Column("min_floor_units", sa.Integer, nullable=False, server_default="0"), sa.Column("valid_from", sa.Date),
                    sa.Column("revision", sa.Integer, nullable=False, server_default="1"), sa.Column("changed_by", sa.String(120), nullable=False),
                    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("policy_override_requests", sa.Column("id", sa.String(36), primary_key=True), sa.Column("variant_id", sa.Integer, nullable=False),
                    sa.Column("field", sa.String(12), nullable=False), sa.Column("recommended_value", sa.Integer, nullable=False),
                    sa.Column("requested_value", sa.Integer, nullable=False), sa.Column("reason", sa.String(500), nullable=False),
                    sa.Column("status", sa.String(10), nullable=False, server_default="pending"), sa.Column("requested_by", sa.String(120), nullable=False),
                    sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False), sa.Column("decided_by", sa.String(120)),
                    sa.Column("decided_at", sa.DateTime(timezone=True)),
                    sa.Column("recommendation_changed", sa.Boolean, nullable=False, server_default=sa.false()))
    op.create_index("ix_policy_override_requests_variant_id", "policy_override_requests", ["variant_id"])


def downgrade() -> None:
    op.drop_index("ix_policy_override_requests_variant_id", table_name="policy_override_requests")
    for t in ("policy_override_requests", "stocking_settings", "budget_caps", "policy_sets"):
        op.drop_table(t)
