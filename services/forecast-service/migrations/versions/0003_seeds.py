"""predictive seed datasets, import pipeline tables and hash-chained audit (MMI 002).

Revision ID: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("seed_mappings", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(120), nullable=False, unique=True),
                    sa.Column("column_map", sa.JSON, nullable=False), sa.Column("created_by", sa.String(120), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("seed_datasets", sa.Column("id", sa.String(36), primary_key=True), sa.Column("version", sa.Integer, nullable=False, unique=True),
                    sa.Column("name", sa.String(200)), sa.Column("status", sa.String(14), nullable=False), sa.Column("origin", sa.String(9), nullable=False),
                    sa.Column("file_sha256", sa.String(64), nullable=False), sa.Column("file_ref", sa.String(300)),
                    sa.Column("uploader", sa.String(120), nullable=False), sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("activated_by", sa.String(120)), sa.Column("activated_at", sa.DateTime(timezone=True)), sa.Column("supersedes_id", sa.String(36)),
                    sa.Column("mapping_id", sa.String(36), sa.ForeignKey("seed_mappings.id")),
                    sa.Column("accepted_count", sa.Integer, nullable=False, server_default="0"), sa.Column("quarantined_count", sa.Integer, nullable=False, server_default="0"),
                    sa.Column("rejected_count", sa.Integer, nullable=False, server_default="0"), sa.Column("kind_summary", sa.JSON),
                    sa.Column("row_count", sa.Integer, nullable=False, server_default="0"))
    op.create_index("uq_seed_datasets_one_active", "seed_datasets", ["status"], unique=True, postgresql_where=sa.text("status = 'active'"),
                    sqlite_where=sa.text("status = 'active'"))
    op.create_table("seed_rows", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
                    sa.Column("dataset_id", sa.String(36), sa.ForeignKey("seed_datasets.id"), nullable=False), sa.Column("row_no", sa.Integer, nullable=False),
                    sa.Column("variant_id", sa.Integer, nullable=False), sa.Column("day", sa.Date, nullable=False), sa.Column("warehouse_external_id", sa.String(40)),
                    sa.Column("quantity", sa.Numeric(18, 4), nullable=False), sa.Column("kind", sa.String(20), nullable=False),
                    sa.Column("provenance_label", sa.String(200), nullable=False),
                    sa.UniqueConstraint("dataset_id", "variant_id", "day", "kind", name="uq_seed_rows_natural"))
    op.create_index("ix_seed_rows_dataset_id", "seed_rows", ["dataset_id"])
    op.create_table("seed_quarantine", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
                    sa.Column("dataset_id", sa.String(36), sa.ForeignKey("seed_datasets.id"), nullable=False), sa.Column("row_no", sa.Integer, nullable=False),
                    sa.Column("reason_key", sa.String(60), nullable=False), sa.Column("reason_params", sa.JSON), sa.Column("raw_row_hash", sa.String(64)))
    op.create_index("ix_seed_quarantine_dataset_id", "seed_quarantine", ["dataset_id"])
    op.create_table("import_jobs", sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("dataset_id", sa.String(36), sa.ForeignKey("seed_datasets.id"), nullable=False), sa.Column("stage", sa.String(20), nullable=False),
                    sa.Column("state", sa.String(12), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)),
                    sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("error_key", sa.String(60)),
                    sa.Column("params", sa.JSON), sa.Column("queued_at", sa.DateTime(timezone=True)), sa.Column("requested_by", sa.String(120)))
    op.create_index("ix_import_jobs_dataset_id", "import_jobs", ["dataset_id"])
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
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_events_no_truncate ON audit_events")
        op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
        op.execute("DROP FUNCTION IF EXISTS forbid_change()")
    for ix, t in (("ix_import_jobs_dataset_id", "import_jobs"), ("ix_seed_quarantine_dataset_id", "seed_quarantine"), ("ix_seed_rows_dataset_id", "seed_rows")):
        op.drop_index(ix, table_name=t)
    op.drop_index("uq_seed_datasets_one_active", table_name="seed_datasets")
    for t in ("audit_events", "import_jobs", "seed_quarantine", "seed_rows", "seed_datasets", "seed_mappings"):
        op.drop_table(t)
