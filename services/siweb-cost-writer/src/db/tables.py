"""Core tables for schema ``costwrite`` (mirrors migrations/versions/0001_costwrite.py)."""

from __future__ import annotations

from mmi_common.outbox import inbox_table, outbox_table
from sqlalchemy import JSON, BigInteger, Column, DateTime, Integer, MetaData, String, Table, UniqueConstraint

metadata = MetaData()

write_attempts = Table(
    "write_attempts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("request_id", String(36), nullable=False, index=True),
    Column("attempt", Integer, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("outcome", String(16), nullable=False),         # sent / succeeded / retrying / failed / pending_link / refused
    Column("http_status", Integer),
    Column("error", String(200)),
    UniqueConstraint("request_id", "attempt", "outcome", name="uq_attempt"),
)
writer_audit = Table(
    "writer_audit", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("request_id", String(36), nullable=False),
    Column("actor_ref", String(120), nullable=False),      # the buyer who released the write (reference only)
    Column("action", String(40), nullable=False),
    Column("product_id", Integer),
    Column("supplier_contact_id", Integer),
    Column("previous_cost_cents", String(40)),
    Column("new_cost_cents", String(40)),
    Column("detail", JSON),
    Column("prev_hash", String(64), nullable=False, unique=True),
    Column("hash", String(64), nullable=False),
)
outbox = outbox_table(metadata)
inbox = inbox_table(metadata)
