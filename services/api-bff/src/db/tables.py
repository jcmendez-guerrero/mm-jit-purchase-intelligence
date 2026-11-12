"""Tables for schema ``bff`` (mirrors migrations/versions/0001_roles.py). Identity data only: no business rules."""

from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, Index, Integer, MetaData, String, Table, text

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
    Column("revision", Integer, nullable=False),                         # the user_roles revision this snapshot represents (ordering guard downstream)
    Column("status", String(10), nullable=False, default="pending"),   # pending / sent / failed
    Column("attempts", Integer, nullable=False, default=0),
    Column("last_error_key", String(80)),
    Column("next_attempt_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("sent_at", DateTime(timezone=True)),
)
Index("ix_role_mirror_outbox_due", role_mirror_outbox.c.status, role_mirror_outbox.c.next_attempt_at)

# ---- feature 010: administration and operations (migration 0002) ----
alerts = Table(
    "alerts", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("condition_key", String(40), nullable=False),
    Column("subject", String(80), nullable=False),                       # a code (source key, job id), never free text
    Column("severity", String(10), nullable=False),                      # warning / critical
    Column("state", String(14), nullable=False, default="open"),         # open / acknowledged / closed
    Column("opened_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("acknowledged_by", String(120)),
    Column("acknowledged_at", DateTime(timezone=True)),
    Column("closed_at", DateTime(timezone=True)),
    Column("reason_code", String(40), nullable=False),
)
Index("uq_alerts_live", alerts.c.condition_key, alerts.c.subject, unique=True,
      sqlite_where=text("state <> 'closed'"), postgresql_where=text("state <> 'closed'"))
ops_snapshots = Table(
    "ops_snapshots", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("kind", String(10), nullable=False),                          # backup / cost / queues
    Column("captured_at", DateTime(timezone=True), nullable=False),
    Column("captured_at_original", String(40), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("status", String(12), nullable=False),                        # ok / unavailable
)
Index("ix_ops_snapshots_kind", ops_snapshots.c.kind, ops_snapshots.c.captured_at)
ops_settings = Table(
    "ops_settings", metadata,
    Column("key", String(40), primary_key=True),
    Column("value", Integer, nullable=False),
    Column("updated_by", String(120), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)
alert_observations = Table(
    "alert_observations", metadata,
    Column("condition_key", String(40), primary_key=True),
    Column("subject", String(80), primary_key=True),
    Column("count", Integer, nullable=False, default=1),                 # consecutive evaluations that saw the condition (repeat rule)
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
)
