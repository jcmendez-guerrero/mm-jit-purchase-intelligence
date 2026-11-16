"""T054, T055: running per-product backtests as jobs (feature 012, FR-016 to FR-018, FR-022).

A job id is derived from the inputs (the series, each product's method, the configuration), so asking again for the same thing reuses the stored
result and adds nothing. Only one full-catalogue job may run at a time: the running marker is committed before the work starts, so another request
sees it, and a database index backs that up if two start together. The work and its results commit together, so a failure leaves no partial result,
marks the job failed and frees the lock. A backtest writes only ``product_backtest``, ``backtest_jobs`` and audit events: forecasts, explanations
and runs are never touched.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from audit import BACKTEST_COMPLETED, BACKTEST_STARTED, append
from db.tables import backtest_jobs, forecast_explanations, forecast_runs, product_backtest
from policies.estimators import BASELINE
from runs.runner import model_versions
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from backtest.product import backtest_product
from backtest.runner import BacktestConfig

log = logging.getLogger("forecast.backtest")


class BacktestConflict(Exception):
    def __init__(self, job_id: str) -> None:
        super().__init__(job_id)
        self.job_id = job_id


class UnknownProduct(Exception):
    pass


class JobFailed(Exception):
    pass


def _methods(engine: Engine) -> dict[int, tuple[str, str | None, str | None]]:
    """Per variant: the method of its latest explanation, with the dataset and configuration versions that run used."""
    with engine.connect() as c:
        run = c.execute(select(forecast_runs.c.id).where(forecast_runs.c.status == "completed").order_by(forecast_runs.c.started_at.desc(), forecast_runs.c.id.desc()).limit(1)).scalar()
        if run is None:
            return {}
        rows = c.execute(select(forecast_explanations).where(forecast_explanations.c.run_id == run)).all()
    return {r.variant_id: (r.method, r.dataset_version_id, r.config_version_id) for r in rows}


def run_backtest(engine: Engine, source: Any, *, scope: str, sku: str | None, actor: str, cfg: BacktestConfig | None = None, now: datetime | None = None) -> dict[str, Any]:
    cfg = cfg or BacktestConfig()
    now = now or datetime.now(UTC)
    clock = time.monotonic()
    try:
        export = source.fetch()
    except Exception as exc:                                           # the series could not be read: the attempt is recorded as failed and nothing else is written
        failed_id = str(uuid.uuid4())
        log.warning("BACKTEST_JOB_FAILED job=%s scope=%s stage=series", failed_id, scope)
        with engine.begin() as c:
            c.execute(insert(backtest_jobs).values(id=failed_id, scope=scope, status="failed", requested_by=actor, started_at=now, finished_at=now))
        raise JobFailed(failed_id) from exc
    series =[s for s in export["series"] if scope == "catalogue" or s.get("sku") == sku]
    if scope == "product" and not series:
        raise UnknownProduct(sku or "")
    methods = _methods(engine)
    versions = model_versions()
    digest = hashlib.sha256(json.dumps({"through": export.get("through_day"), "scope": scope, "sku": sku, "cfg": [cfg.horizon, cfg.lead_time, cfg.origins, cfg.step, cfg.min_history, str(cfg.max_censored_share)],
                                        "series": [[s["variant_id"], s["demand"], s["censored"], s["service_level"], methods.get(s["variant_id"], (BASELINE,))[0]] for s in series]},
                                       sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"mmi/backtest/{digest}"))
    with engine.begin() as c:
        existing = c.execute(select(backtest_jobs.c.status, backtest_jobs.c.scope).where(backtest_jobs.c.id == job_id)).first()
        if existing is not None and existing.status == "completed":
            log.info("BACKTEST_JOB_REUSED job=%s scope=%s products=%d", job_id, scope, len(series))
            return {"job_id": job_id, "status": "completed", "reused": True, "products": len(series)}
        if scope == "catalogue":
            running = c.execute(select(backtest_jobs.c.id).where(backtest_jobs.c.scope == "catalogue", backtest_jobs.c.status == "running")).scalar()
            if running is not None:
                log.info("BACKTEST_JOB_REFUSED running=%s", running)
                raise BacktestConflict(running)
        if existing is not None:                                       # a failed attempt of the same inputs: clear the marker and try again
            c.execute(backtest_jobs.delete().where(backtest_jobs.c.id == job_id))
    try:
        with engine.begin() as c:                                      # commits now, so other requests see the job as running
            c.execute(insert(backtest_jobs).values(id=job_id, scope=scope, status="running", requested_by=actor, started_at=now))
            append(c, actor, BACKTEST_STARTED, "product_backtest", job_id, after={"scope": scope, "products": len(series)}, now=now)
    except IntegrityError as exc:                                      # two catalogue jobs started together: the index lets one through
        with engine.connect() as c:
            running = c.execute(select(backtest_jobs.c.id).where(backtest_jobs.c.scope == "catalogue", backtest_jobs.c.status == "running")).scalar()
        raise BacktestConflict(running or job_id) from exc
    try:
        with engine.begin() as c:
            rows = []
            for s in series:
                method, dataset, config_id = methods.get(s["variant_id"], (BASELINE, None, None))
                r = backtest_product(s, method, cfg)
                rows.append({"backtest_run_id": job_id, "variant_id": s["variant_id"], "sku": s.get("sku"), "periods": r.periods, "wape": r.wape, "bias": r.bias,
                             "baseline_wape": r.baseline_wape, "baseline_bias": r.baseline_bias, "beats_baseline": r.beats_baseline,
                             "model_version": f"{method}@{versions.get(method, 'unknown')}", "dataset_version_id": dataset, "config_version_id": config_id, "created_at": now})
            if rows:
                c.execute(insert(product_backtest), rows)
            c.execute(update(backtest_jobs).where(backtest_jobs.c.id == job_id).values(status="completed", finished_at=datetime.now(UTC)))
            append(c, actor, BACKTEST_COMPLETED, "product_backtest", job_id, after={"scope": scope, "products": len(rows), "flagged": sum(1 for r in rows if not r["beats_baseline"])})
    except Exception as exc:
        log.warning("BACKTEST_JOB_FAILED job=%s scope=%s stage=compute error=%s", job_id, scope, type(exc).__name__)
        with engine.begin() as c:
            c.execute(update(backtest_jobs).where(backtest_jobs.c.id == job_id).values(status="failed", finished_at=datetime.now(UTC)))
        raise JobFailed(job_id) from exc
    log.info("BACKTEST_JOB_DONE job=%s scope=%s products=%d duration_ms=%d", job_id, scope, len(series), (time.monotonic() - clock) * 1000)
    return {"job_id": job_id, "status": "completed", "reused": False, "products": len(series)}
