"""Tables for schema ``bff`` (mirrors migrations/versions/0001_roles.py). Identity data only: no business rules."""

from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, Index, Integer, MetaData, String, Table

metadata = MetaData()

user_roles = Table(
    "user_roles", metadata,
    Column("user_id", String(120), primary_key=True),
    Column("roles", JSON, nullable=False),                               # subset of viewer / buyer / approver / admin
    Column("active", Boolean, nullable=False, default=True),
    Column("revision", Integer, nullable=False, default=1),
    Column("updated_by", String(120), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
audit_events = Table(
    "audit_events", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("ts", DateTime(timezone=True), nullable=False),
    Column("actor", String(120), nullable=False),
    Column("action", String(40), nullable=False),
    Column("entity", String(30), nullable=False),
    Column("entity_id", String(60), nullable=False),
    Column("before", JSON),
    Column("after", JSON),
    Column("prev_hash", String(64), nullable=False, unique=True),
    Column("hash", String(64), nullable=False),
)
role_mirror_outbox = Table(
    "role_mirror_outbox", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("user_id", String(120), nullable=False),
    Column("roles_snapshot", JSON, nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("status", String(10), nullable=False, default="pending"),   # pending / sent / failed
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_error_key", String(80)),
    Column("next_attempt_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("sent_at", DateTime(timezone=True)),
)
Index("ix_role_mirror_outbox_due", role_mirror_outbox.c.status, role_mirror_outbox.c.next_attempt_at)
