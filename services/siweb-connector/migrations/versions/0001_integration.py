"""integration schema: runs, checkpoints, mappings, quarantine, raw payload index, rate log, outbox.

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True)),
        sa.Column("window_end", sa.DateTime(timezone=True)),
        sa.Column("frozen_date_to", sa.String(10)),
        sa.Column("status", sa.String(12), nullable=False),  # running/committed/partial/failed
        sa.Column("counts_fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("counts_stored", sa.Integer, nullable=False, server_default="0"),
        sa.Column("counts_errors", sa.Integer, nullable=False, server_default="0"),
        sa.Column("siweb_total", sa.Integer),
        sa.Column("reconciled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("requests_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "sync_checkpoints",
        sa.Column("kind", sa.String(20), primary_key=True),
        sa.Column("last_movement_id", sa.BigInteger),
        sa.Column("last_created_at", sa.DateTime(timezone=True)),
        sa.Column("backfill_cursor", sa.JSON),
    )
    op.create_table(
        "external_mappings",
        sa.Column("entity", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(40), nullable=False),
        sa.Column("internal_id", sa.String(40), nullable=False),
        sa.PrimaryKeyConstraint("entity", "external_id"),
    )
    op.create_table(
        "import_errors",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("sync_runs.id"), nullable=False),
        sa.Column("entity", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(40), nullable=False),
        sa.Column("error_code", sa.String(40), nullable=False),
        sa.Column("detail", sa.String(200), nullable=False),
        sa.Column("blocking", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),  # open/resolved/ignored
        sa.Column("resolved_by", sa.String(80)),
        sa.UniqueConstraint("entity", "external_id", "error_code", name="uq_import_error"),
    )
    op.create_table(
        "raw_payload_index",
        sa.Column("blob_uri", sa.String(300), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("sync_runs.id"), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "rate_budget_log",
        sa.Column("hour_bucket", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("denied", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "outbox",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(120), nullable=False),
        sa.Column("envelope", sa.JSON, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    for t in ("outbox", "rate_budget_log", "raw_payload_index", "import_errors", "external_mappings", "sync_checkpoints", "sync_runs"):
        op.drop_table(t)
