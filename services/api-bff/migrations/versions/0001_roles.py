"""durable user roles, hash-chained audit and the role-mirror outbox.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("user_roles", sa.Column("user_id", sa.String(120), primary_key=True), sa.Column("roles", sa.JSON, nullable=False),
                    sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
                    sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
                    sa.Column("updated_by", sa.String(120), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("audit_events", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
                    sa.Column("ts", sa.DateTime(timezone=True), nullable=False), sa.Column("actor", sa.String(120), nullable=False),
                    sa.Column("action", sa.String(40), nullable=False), sa.Column("entity", sa.String(30), nullable=False),
                    sa.Column("entity_id", sa.String(60), nullable=False), sa.Column("before", sa.JSON), sa.Column("after", sa.JSON),
                    sa.Column("prev_hash", sa.String(64), nullable=False, unique=True), sa.Column("hash", sa.String(64), nullable=False))
    op.create_table("role_mirror_outbox", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
                    sa.Column("user_id", sa.String(120), nullable=False), sa.Column("roles_snapshot", sa.JSON, nullable=False),
                    sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
                    sa.Column("revision", sa.Integer, nullable=False),
                    sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
                    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"), sa.Column("last_error_key", sa.String(80)),
                    sa.Column("next_attempt_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("sent_at", sa.DateTime(timezone=True)))
    op.create_index("ix_role_mirror_outbox_due", "role_mirror_outbox", ["status", "next_attempt_at"])
    if op.get_bind().dialect.name == "postgresql":      # append-only audit, enforced for every role including the owner
        op.execute("""CREATE FUNCTION forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
                      BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE = 'integrity_constraint_violation'; END $$""")
        op.execute("CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION forbid_change()")
        op.execute("CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events FOR EACH STATEMENT EXECUTE FUNCTION forbid_change()")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_events_no_truncate ON audit_events")
        op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
        op.execute("DROP FUNCTION IF EXISTS forbid_change()")
    op.drop_index("ix_role_mirror_outbox_due", table_name="role_mirror_outbox")
    for t in ("role_mirror_outbox", "audit_events", "user_roles"):
        op.drop_table(t)
