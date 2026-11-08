"""executive dashboard: capital, demand, forecast and data origin stored with the daily KPI history (MMI 006, T007).

Extends agg_daily_kpis instead of adding a table (audit decision). Existing rows keep NULL for the new figures and origin 'erp_sync'.

Revision ID: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agg_daily_kpis", sa.Column("capital_tied_up", sa.Numeric(18, 4), nullable=True))
    op.add_column("agg_daily_kpis", sa.Column("demand_units", sa.Integer, nullable=True))
    op.add_column("agg_daily_kpis", sa.Column("forecast_units", sa.Numeric(18, 2), nullable=True))
    op.add_column("agg_daily_kpis", sa.Column("origin", sa.String(20), nullable=False, server_default="erp_sync"))


def downgrade() -> None:
    with op.batch_alter_table("agg_daily_kpis") as b:
        b.drop_column("origin")
        b.drop_column("forecast_units")
        b.drop_column("demand_units")
        b.drop_column("capital_tied_up")
