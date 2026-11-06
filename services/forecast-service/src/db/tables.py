"""Core tables for schema ``forecasting`` (mirrors migrations/versions/0001_forecasting.py)."""

from __future__ import annotations

from mmi_common.outbox import inbox_table, outbox_table
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
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
    Column("dataset_version_id", String(36)),                          # exact seed dataset used (MMI 002)
    Column("parameter_version_ids", JSON),                              # forecast parameter versions used
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


# ---- MMI 002: predictive seed datasets (migration 0003) and parameters / accuracy (0004) ----
seed_mappings = Table(
    "seed_mappings", metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(120), nullable=False, unique=True),
    Column("column_map", JSON, nullable=False),                          # source header -> canonical field
    Column("created_by", String(120), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
seed_datasets = Table(
    "seed_datasets", metadata,
    Column("id", String(36), primary_key=True),
    Column("version", Integer, nullable=False, unique=True),
    Column("name", String(200)),
    Column("status", String(14), nullable=False),                        # uploaded / validated / approved / active / superseded / rolled_back / rejected
    Column("origin", String(9), nullable=False),                         # synthetic / real; a dataset never mixes them
    Column("file_sha256", String(64), nullable=False),
    Column("file_ref", String(300)),                                     # private quarantine container reference; never a public URL
    Column("uploader", String(120), nullable=False),
    Column("uploaded_at", DateTime(timezone=True), nullable=False),
    Column("activated_by", String(120)),
    Column("activated_at", DateTime(timezone=True)),
    Column("supersedes_id", String(36)),
    Column("mapping_id", String(36), ForeignKey("seed_mappings.id")),
    Column("accepted_count", Integer, nullable=False, default=0),
    Column("quarantined_count", Integer, nullable=False, default=0),
    Column("rejected_count", Integer, nullable=False, default=0),
    Column("kind_summary", JSON),
)
Index("uq_seed_datasets_one_active", seed_datasets.c.status, unique=True, postgresql_where=seed_datasets.c.status == "active",
      sqlite_where=seed_datasets.c.status == "active")
seed_rows = Table(
    "seed_rows", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("dataset_id", String(36), ForeignKey("seed_datasets.id"), nullable=False, index=True),
    Column("row_no", Integer, nullable=False),
    Column("variant_id", Integer, nullable=False),                       # Siweb variant_id
    Column("day", Date, nullable=False),
    Column("warehouse_external_id", String(40)),
    Column("quantity", Numeric(18, 4), nullable=False),
    Column("kind", String(20), nullable=False),                          # observed_external / estimated / manual_forecast
    Column("provenance_label", String(200), nullable=False),
    UniqueConstraint("dataset_id", "variant_id", "day", "kind", name="uq_seed_rows_natural"),
)
seed_quarantine = Table(
    "seed_quarantine", metadata,
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True),
    Column("dataset_id", String(36), ForeignKey("seed_datasets.id"), nullable=False, index=True),
    Column("row_no", Integer, nullable=False),
    Column("reason_key", String(60), nullable=False),                    # stable error code; the SPA renders Spanish
    Column("reason_params", JSON),
    Column("raw_row_hash", String(64)),                                  # never the raw row, notes or tax identifiers
)
import_jobs = Table(
    "import_jobs", metadata,
    Column("id", String(36), primary_key=True),
    Column("dataset_id", String(36), ForeignKey("seed_datasets.id"), nullable=False, index=True),
    Column("stage", String(20), nullable=False),                         # parse / validate / dry_run / activate / rollback
    Column("state", String(12), nullable=False),                         # queued / running / done / failed
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("error_key", String(60)),
)
forecast_parameters = Table(
    "forecast_parameters", metadata,
    Column("id", String(36), primary_key=True),
    Column("scope", String(40), nullable=False),
    Column("key", String(60), nullable=False),
    Column("value", JSON, nullable=False),
    Column("valid_from", Date, nullable=False),
    Column("valid_to", Date),
    Column("revision", Integer, nullable=False, default=1),
    Column("changed_by", String(120), nullable=False),
    UniqueConstraint("scope", "key", "valid_from", name="uq_forecast_parameters_effective"),
)
forecast_accuracy = Table(
    "forecast_accuracy", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String(36), ForeignKey("forecast_runs.id"), nullable=False),
    Column("segment", String(20), nullable=False),
    Column("metric", String(20), nullable=False),                        # wape / bias / stockout_rate
    Column("value", Numeric(12, 6), nullable=False),
    Column("window_days", Integer),
    UniqueConstraint("run_id", "segment", "metric", name="uq_forecast_accuracy_natural"),
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
