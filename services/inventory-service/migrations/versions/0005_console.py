"""category history, demand rules, dashboard aggregates, lot-cost projection and hash-chained audit (MMI 002).

Revision ID: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("variants", sa.Column("price_confirmed_at", sa.DateTime(timezone=True)))
    op.add_column("products", sa.Column("family", sa.String(120)))
    op.create_table("segment_history", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True), sa.Column("variant_id", sa.Integer, nullable=False),
                    sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("abc", sa.String(1), nullable=False),
                    sa.Column("xyz", sa.String(1), nullable=False), sa.Column("pattern", sa.String(14), nullable=False),
                    sa.Column("critical", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("reason_key", sa.String(60), nullable=False),
                    sa.Column("run_id", sa.String(36), nullable=False))
    op.create_index("ix_segment_history_variant_id", "segment_history", ["variant_id"])
    op.create_table("demand_exclusions", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("variant_id", sa.Integer),
                    sa.Column("from_day", sa.Date, nullable=False), sa.Column("to_day", sa.Date, nullable=False), sa.Column("reason", sa.String(500), nullable=False),
                    sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()), sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
                    sa.Column("changed_by", sa.String(120), nullable=False))
    op.create_table("censoring_rules", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("rule", sa.String(40), nullable=False),
                    sa.Column("value", sa.Integer, nullable=False), sa.Column("valid_from", sa.Date, nullable=False),
                    sa.Column("revision", sa.Integer, nullable=False, server_default="1"), sa.Column("changed_by", sa.String(120), nullable=False))
    op.create_table("agg_daily_kpis", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("day", sa.Date, nullable=False),
                    sa.Column("warehouse_id", sa.Integer), sa.Column("category_id", sa.String(40)), sa.Column("supplier_id", sa.String(36)),
                    sa.Column("inventory_value", sa.Numeric(18, 4), nullable=False), sa.Column("valued_with_estimate_count", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("coverage_days_avg", sa.Numeric(10, 2)), sa.Column("stockout_risk_count", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("expiring_value", sa.Numeric(18, 4), nullable=False, server_default="0"), sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_agg_daily_kpis_day", "agg_daily_kpis", ["day"])
    op.create_table("agg_demand_trend", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("day", sa.Date, nullable=False),
                    sa.Column("scope_key", sa.String(40), nullable=False), sa.Column("actual_qty", sa.Numeric(18, 4)), sa.Column("estimated_qty", sa.Numeric(18, 4)),
                    sa.Column("forecast_mean", sa.Numeric(18, 4)), sa.Column("forecast_low", sa.Numeric(18, 4)), sa.Column("forecast_high", sa.Numeric(18, 4)))
    op.create_index("ix_agg_demand_trend_day", "agg_demand_trend", ["day"])
    op.create_table("agg_abc_xyz", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("day", sa.Date, nullable=False),
                    sa.Column("abc", sa.String(1), nullable=False), sa.Column("xyz", sa.String(1), nullable=False), sa.Column("variant_count", sa.Integer, nullable=False),
                    sa.Column("value", sa.Numeric(18, 4), nullable=False))
    op.create_index("ix_agg_abc_xyz_day", "agg_abc_xyz", ["day"])
    op.create_table("lot_cost_projection", sa.Column("variant_id", sa.Integer, primary_key=True, autoincrement=False),
                    sa.Column("supplier_id", sa.String(36), primary_key=True), sa.Column("lot", sa.String(60), primary_key=True),
                    sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False), sa.Column("source", sa.String(20), nullable=False),
                    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("audit_events", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
                    sa.Column("ts", sa.DateTime(timezone=True), nullable=False), sa.Column("actor", sa.String(120), nullable=False),
                    sa.Column("action", sa.String(40), nullable=False), sa.Column("entity", sa.String(30), nullable=False),
                    sa.Column("entity_id", sa.String(60), nullable=False), sa.Column("before", sa.JSON), sa.Column("after", sa.JSON),
                    sa.Column("prev_hash", sa.String(64), nullable=False, unique=True), sa.Column("hash", sa.String(64), nullable=False))
    if op.get_bind().dialect.name == "postgresql":      # append-only audit, enforced for every role including the owner
        op.execute("""CREATE FUNCTION forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
                      BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = 'integrity_constraint_violation'; END $$""")
        op.execute("CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION forbid_change()")
        op.execute("CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events FOR EACH STATEMENT EXECUTE FUNCTION forbid_change()")


def downgrade() -> None:
    op.drop_column("variants", "price_confirmed_at")
    op.drop_column("products", "family")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_events_no_truncate ON audit_events")
        op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
        op.execute("DROP FUNCTION IF EXISTS forbid_change()")
    for ix, t in (("ix_agg_abc_xyz_day", "agg_abc_xyz"), ("ix_agg_demand_trend_day", "agg_demand_trend"), ("ix_agg_daily_kpis_day", "agg_daily_kpis"),
                  ("ix_segment_history_variant_id", "segment_history")):
        op.drop_index(ix, table_name=t)
    for t in ("audit_events", "lot_cost_projection", "agg_abc_xyz", "agg_demand_trend", "agg_daily_kpis", "censoring_rules", "demand_exclusions", "segment_history"):
        op.drop_table(t)
