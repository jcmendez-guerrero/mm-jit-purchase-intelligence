"""Core tables for schema ``forecasting`` (mirrors migrations/versions/0001_forecasting.py)."""

from __future__ import annotations

from mmi_common.outbox import inbox_table, outbox_table
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

forecast_runs = Table(
    "forecast_runs", metadata,
    Column("id", String(36), primary_key=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("through_day", String(10)),
    Column("model_versions", JSON, nullable=False),
    Column("input_hash", String(64), nullable=False, index=True),
    Column("config", JSON, nullable=False),
    Column("status", String(12), nullable=False),
    Column("total_count", Integer, nullable=False, default=0),
    Column("eligible_count", Integer, nullable=False, default=0),
)
forecast_values = Table(
    "forecast_values", metadata,
    Column("run_id", String(36), primary_key=True),
    Column("variant_id", Integer, primary_key=True, autoincrement=False),
    Column("horizon_days", Integer, primary_key=True, autoincrement=False),
    Column("mean", Float),                      # NULL when not forecast-eligible: no point forecast is published
    Column("quantiles", JSON, nullable=False),  # level -> units; {"min","max"} for fallback rows
    Column("policy_used", String(30), nullable=False),
    Column("eligible", Boolean, nullable=False),
    Column("reasons", String(200), nullable=False),
    Column("service_level", Numeric(5, 4), nullable=False),
)
backtest_metrics = Table(
    "backtest_metrics", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String(36), nullable=False),
    Column("segment", String(14), nullable=False),
    Column("policy", String(30), nullable=False),
    Column("stockout_cost", Numeric(18, 4), nullable=False),
    Column("holding_cost", Numeric(18, 4), nullable=False),
    Column("expiry_cost", Numeric(18, 4), nullable=False),
    Column("windows", Integer, nullable=False),
    Column("adopted", Boolean, nullable=False),
    UniqueConstraint("run_id", "segment", "policy", name="uq_backtest"),
)
model_registry = Table(
    "model_registry", metadata,
    Column("name", String(30), primary_key=True),
    Column("version", String(20), primary_key=True),
    Column("params_hash", String(64), nullable=False),
    Column("artifact_uri", String(300)),
    Column("adopted_for_segment", String(120)),   # comma-separated patterns
)
outbox = outbox_table(metadata)
inbox = inbox_table(metadata)
