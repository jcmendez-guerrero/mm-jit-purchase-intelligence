"""T067/T069: a versioned, reproducible forecast run.

Inputs come from inventory-service's series export. The run hashes its inputs, configuration and model versions, so the
same inputs give the same hash and the same outputs, and a repeat is recognised instead of duplicated. Eligible products
get a point forecast with quantiles from the policy adopted for their pattern; ineligible ones get only a conservative
min/max and the reason, never a forecast. forecast.completed.v1 goes out through the outbox in the same transaction.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from backtest.runner import BacktestConfig, BacktestSeries, compare, select_policies
from db.tables import backtest_metrics, forecast_runs, forecast_values, model_registry, outbox
from mmi_common.bus import new_envelope
from mmi_common.outbox import enqueue
from mmi_common.time import get_correlation_id, set_correlation_id
from policies.base import VERSION, build_plan, prepare_history
from policies.estimators import BASELINE, CANDIDATES, POLICIES
from policies.fallback import NAME as FALLBACK
from policies.fallback import conservative_plan
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine

from runs.eligibility import decide

EVENT_TYPE = "forecast.completed.v1"
SUBSCRIPTIONS = {EVENT_TYPE: ["procurement-in"], "forecast.seed.activated.v1": ["forecast-in"]}
DEFAULT_HORIZONS = (7, 14, 21, 28, 42)


class SeriesSource(Protocol):
    def fetch(self) -> dict[str, Any]: ...


class BlobWriter(Protocol):
    def put(self, name: str, data: bytes) -> str: ...


@dataclass(frozen=True)
class RunConfig:
    horizons: tuple[int, ...] = DEFAULT_HORIZONS
    lead_time: int = 7
    backtest: BacktestConfig = field(default_factory=BacktestConfig)

    def as_json(self) -> dict[str, Any]:
        b = self.backtest
        return {"horizons": list(self.horizons), "lead_time": self.lead_time,
                "backtest": {"horizon": b.horizon, "lead_time": b.lead_time, "origins": b.origins, "step": b.step, "min_history": b.min_history,
                             "min_gain": str(b.min_gain), "min_windows": b.min_windows, "max_censored_share": b.max_censored_share,
                             "costs": {k: str(v) for k, v in vars(b.costs).items()}}}


@dataclass
class RunResult:
    run_id: str
    input_hash: str
    reused: bool
    total: int
    eligible: int
    adopted: dict[str, str]


def model_versions() -> dict[str, str]:
    return {**{p.name: p.version for p in CANDIDATES}, FALLBACK: VERSION}


def input_hash(export: dict[str, Any], cfg: RunConfig) -> str:
    body = {"through_day": export.get("through_day"), "series": export["series"], "config": cfg.as_json(), "versions": model_versions()}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def run_forecast(engine: Engine, source: SeriesSource, writer: BlobWriter, cfg: RunConfig | None = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> RunResult:
    with engine.begin() as conn:
        return run_forecast_conn(conn, source, writer, cfg, clock)


def run_forecast_conn(conn: Connection, source: SeriesSource, writer: BlobWriter, cfg: RunConfig | None = None,
                      clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> RunResult:
    """One run inside the caller's transaction (the queue consumer's, so the inbox row and the run commit together)."""
    versions: dict[str, int] | None = None
    if cfg is None:                              # parameters in force today (FR-016); an explicit config is used as given
        from parameters import config_from_parameters

        cfg, versions = config_from_parameters(conn, clock().date())
    export = source.fetch()
    from runs.accuracy import evaluate_previous

    evaluate_previous(conn, export)          # score the previous run against what really happened (real demand only, before any seed is applied)
    from runs.seeds import SeedReport, apply_seeds, load_active

    seeds, report = load_active(conn), SeedReport()
    if seeds is not None:                      # the active seed dataset extends short histories only; the run records which one it used
        series_with_seeds, report = apply_seeds(export["series"], seeds, cfg.backtest.min_history)
        export = {**export, "series": series_with_seeds}
    digest = input_hash(export, cfg)
    done = conn.execute(select(forecast_runs).where(forecast_runs.c.input_hash == digest, forecast_runs.c.status == "completed")).first()
    if done:  # identical inputs, configuration and models: nothing new to compute or announce
        return RunResult(done.id, digest, True, done.total_count, done.eligible_count, {})
    run_id, started = str(uuid.uuid4()), clock()
    series = export["series"]

    candidates = [
        BacktestSeries(s["variant_id"], s["demand"], s["censored"], Decimal(s["price"]), s["segment"]["pattern"], float(s["service_level"]))
        for s in series if s.get("segment") and s["segment"]["forecast_eligible"] and Decimal(s["price"]) > 0
    ]
    results = compare(candidates, CANDIDATES, cfg.backtest)
    adopted = select_policies(results, cfg.backtest)

    rows: list[dict[str, Any]] = []
    eligible = 0
    for s in series:
        d = decide(s.get("segment"), adopted)
        history = prepare_history(s["demand"], s["censored"])
        level = float(s["service_level"])
        crit = bool(s.get("clinical_critical"))
        eligible += d.eligible
        for h in cfg.horizons:
            if d.eligible:
                rate = POLICIES[d.policy].rate(history)
                policy_used = d.policy
                if rate is None:   # e.g. seasonal naive without a year of history: fall back to the baseline estimator
                    rate, policy_used = POLICIES[BASELINE].rate(history) or 0.0, BASELINE
                plan = build_plan(policy_used, rate, history, h, min(cfg.lead_time, h), level)
                rows.append({"run_id": run_id, "variant_id": s["variant_id"], "horizon_days": h, "mean": plan.mean_horizon, "quantiles": plan.quantiles,
                             "policy_used": policy_used, "eligible": True, "reasons": "seed_used" if s["variant_id"] in report.used else "", "service_level": Decimal(str(level))})
            else:
                fb = conservative_plan(history, h, min(cfg.lead_time, h), level, crit).plan
                rows.append({"run_id": run_id, "variant_id": s["variant_id"], "horizon_days": h, "mean": None,
                             "quantiles": {"min": fb.reorder_point, "max": fb.order_up_to}, "policy_used": FALLBACK, "eligible": False,
                             "reasons": ",".join(d.reasons), "service_level": Decimal(str(level))})

    cid = get_correlation_id() or set_correlation_id()
    conn.execute(insert(forecast_runs).values(
        id=run_id, started_at=started, through_day=export.get("through_day"), model_versions=model_versions(), input_hash=digest,
        config={**cfg.as_json(), **({} if seeds is None else {"seed": {"dataset_id": seeds.dataset_id, "variants_used": len(report.used), "overlap_variants": report.overlap_variants, "overlap_days": report.overlap_days, "retired_variants": len(report.retired)}})}, status="running", total_count=len(series), eligible_count=eligible,
        parameter_version_ids=versions or None, dataset_version_id=None if seeds is None else seeds.dataset_id))
    if rows:
        conn.execute(insert(forecast_values), rows)
    _store_backtests(conn, run_id, results, adopted)
    payload = json.dumps({"run_id": run_id, "input_hash": digest, "eligible_count": eligible, "dataset_version_id": None if seeds is None else seeds.dataset_id}, sort_keys=True, separators=(",", ":")).encode()
    uri = writer.put(f"events/forecast/{run_id}.json", payload)
    enqueue(conn, outbox, new_envelope(EVENT_TYPE, run_id, payload, uri, cid))
    conn.execute(update(forecast_runs).where(forecast_runs.c.id == run_id).values(status="completed", finished_at=clock()))
    return RunResult(run_id, digest, False, len(series), eligible, adopted)


def _store_backtests(conn: Connection, run_id: str, results: Any, adopted: dict[str, str]) -> None:
    for seg, per in results.items():
        for name, cost in per.items():
            conn.execute(insert(backtest_metrics).values(
                run_id=run_id, segment=seg, policy=name, stockout_cost=cost.stockout, holding_cost=cost.holding, expiry_cost=cost.expiry,
                windows=cost.windows, adopted=adopted.get(seg) == name))
    for name, p in POLICIES.items():
        params = hashlib.sha256(json.dumps(vars(p), sort_keys=True, default=str).encode()).hexdigest()
        segments = sorted(seg for seg, chosen in adopted.items() if chosen == name)
        exists = conn.execute(select(model_registry.c.name).where(model_registry.c.name == name, model_registry.c.version == p.version)).first()
        if exists is None:
            conn.execute(insert(model_registry).values(name=name, version=p.version, params_hash=params, adopted_for_segment=",".join(segments) or None))
        else:
            conn.execute(update(model_registry).where(model_registry.c.name == name, model_registry.c.version == p.version)
                         .values(adopted_for_segment=",".join(segments) or None))
