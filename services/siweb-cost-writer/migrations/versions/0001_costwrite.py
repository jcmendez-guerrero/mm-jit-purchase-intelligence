"""costwrite schema: write attempts, hash-chained writer audit, outbox/inbox.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("write_attempts", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("request_id", sa.String(36), nullable=False),
                    sa.Column("attempt", sa.Integer, nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("outcome", sa.String(16), nullable=False), sa.Column("http_status", sa.Integer), sa.Column("error", sa.String(200)),
                    sa.UniqueConstraint("request_id", "attempt", "outcome", name="uq_attempt"))
    op.create_index("ix_attempts_request", "write_attempts", ["request_id"])
    op.create_table("writer_audit", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True), sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("request_id", sa.String(36), nullable=False), sa.Column("actor_ref", sa.String(120), nullable=False),
                    sa.Column("action", sa.String(40), nullable=False), sa.Column("product_id", sa.Integer), sa.Column("supplier_contact_id", sa.Integer),
                    sa.Column("previous_cost_cents", sa.String(40)), sa.Column("new_cost_cents", sa.String(40)), sa.Column("detail", sa.JSON),
                    sa.Column("prev_hash", sa.String(64), nullable=False, unique=True), sa.Column("hash", sa.String(64), nullable=False))
    op.create_table("outbox", sa.Column("event_id", sa.String(36), primary_key=True), sa.Column("type", sa.String(120), nullable=False),
                    sa.Column("envelope", sa.JSON, nullable=False), sa.Column("status", sa.String(12), nullable=False),
                    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("sent_at", sa.DateTime(timezone=True)))
    op.create_table("inbox", sa.Column("event_id", sa.String(36), primary_key=True), sa.Column("type", sa.String(120), nullable=False),
                    sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    for t in ("inbox", "outbox", "writer_audit", "write_attempts"):
        op.drop_table(t)
