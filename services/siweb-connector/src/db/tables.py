"""Core table definitions for schema ``integration`` (mirrors migrations/versions/0001_integration.py).

The schema is selected through the role's search_path, so tables carry no schema name here
(this also lets the unit tests run on SQLite).
"""

from __future__ import annotations

from mmi_common.outbox import outbox_table
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

sync_runs = Table(
    "sync_runs", metadata,
    Column("id", String(36), primary_key=True),
    Column("kind", String(20), nullable=False),
    Column("window_start", DateTime(timezone=True)),
    Column("window_end", DateTime(timezone=True)),
    Column("frozen_date_to", String(10)),
    Column("status", String(12), nullable=False),
    Column("counts_fetched", Integer, nullable=False, default=0),
    Column("counts_stored", Integer, nullable=False, default=0),
    Column("counts_errors", Integer, nullable=False, default=0),
    Column("siweb_total", Integer),
    Column("reconciled", Boolean, nullable=False, default=False),
    Column("requests_used", Integer, nullable=False, default=0),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
)
sync_checkpoints = Table(
    "sync_checkpoints", metadata,
    Column("kind", String(20), primary_key=True),
    Column("last_movement_id", BigInteger),
    Column("last_created_at", DateTime(timezone=True)),
    Column("backfill_cursor", JSON),
)
external_mappings = Table(
    "external_mappings", metadata,
    Column("entity", String(20), primary_key=True),
    Column("external_id", String(40), primary_key=True),
    Column("internal_id", String(40), nullable=False),
)
import_errors = Table(
    "import_errors", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String(36), ForeignKey("sync_runs.id"), nullable=False),
    Column("entity", String(20), nullable=False),
    Column("external_id", String(40), nullable=False),
    Column("error_code", String(40), nullable=False),
    Column("detail", String(200), nullable=False),
    Column("blocking", Boolean, nullable=False, default=True),
    Column("status", String(10), nullable=False, default="open"),
    Column("resolved_by", String(80)),
    UniqueConstraint("entity", "external_id", "error_code", name="uq_import_error"),
)
raw_payload_index = Table(
    "raw_payload_index", metadata,
    Column("blob_uri", String(300), primary_key=True),
    Column("run_id", String(36), ForeignKey("sync_runs.id"), nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)
rate_budget_log = Table(
    "rate_budget_log", metadata,
    Column("hour_bucket", DateTime(timezone=True), primary_key=True),
    Column("used", Integer, nullable=False, default=0),
    Column("denied", Integer, nullable=False, default=0),
)
outbox = outbox_table(metadata)
