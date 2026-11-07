"""T114: background validation of large seed files (hybrid, decided 2026-11-06).

Up to ``SYNC_ROWS`` rows are validated inside the upload request. Larger files are queued here and processed by the scale-to-zero worker.
A job carries only the mapping and who asked, never file content. Running a stage again is safe: validation replaces the dataset's rows,
a queued or running job is reused rather than duplicated, and a job left ``running`` for too long is picked up again.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from typing import Any

from audit import append
from db.tables import import_jobs, seed_datasets
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine
from upload_settings import ParseLimits

from seeds.lifecycle import BlobStore, LifecycleError, validate_dataset
from seeds.storage import SeedFileError

SYNC_ROWS = 10_000
STALE_AFTER = timedelta(minutes=15)
STAGE = "validate"
log = logging.getLogger("forecast.imports")


def enqueue_validation(conn: Connection, dataset_id: str, column_map: dict[str, str], actor: str, mapping_id: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    live = conn.execute(select(import_jobs).where(import_jobs.c.dataset_id == dataset_id, import_jobs.c.stage == STAGE, import_jobs.c.state.in_(("queued", "running")))).first()
    if live is not None:
        return {"job_id": live.id, "state": live.state, "reused": True}
    jid = str(uuid.uuid4())
    conn.execute(import_jobs.insert().values(id=jid, dataset_id=dataset_id, stage=STAGE, state="queued", queued_at=now, requested_by=actor,
                                             params={"column_map": column_map, "mapping_id": mapping_id}))
    return {"job_id": jid, "state": "queued", "reused": False}


def rerun_job(conn: Connection, job_id: str, actor: str, now: datetime | None = None) -> dict[str, Any]:
    """Queue a failed validation job again with the inputs it had. Idempotent: a live job for the dataset is reused, nothing is duplicated."""
    job = conn.execute(select(import_jobs).where(import_jobs.c.id == job_id)).first()
    if job is None:
        raise LifecycleError("import_unknown_job")
    if job.state in ("queued", "running"):
        return {"job_id": job.id, "state": job.state, "reused": True}
    if job.state != "failed" or job.stage != STAGE:
        raise LifecycleError("import_job_not_rerunnable")
    p = job.params or {}
    res = enqueue_validation(conn, job.dataset_id, p.get("column_map", {}), actor, mapping_id=p.get("mapping_id"), now=now)
    if not res["reused"]:
        append(conn, actor, "import.job_rerun", "import_job", res["job_id"], before={"previous_job": job.id, "error_key": job.error_key})
    return res


def process_queued(engine: Engine, store: BlobStore, known_variants: Collection[int], limits: ParseLimits, now: datetime | None = None) -> dict[str, int]:
    """One worker pass. Each job runs in its own transaction, so one failure never blocks the others."""
    now = now or datetime.now(UTC)
    with engine.begin() as conn:                                               # put abandoned jobs back in the queue
        conn.execute(update(import_jobs).where(import_jobs.c.stage == STAGE, import_jobs.c.state == "running", import_jobs.c.started_at < now - STALE_AFTER).values(state="queued"))
        ids = [r.id for r in conn.execute(select(import_jobs.c.id).where(import_jobs.c.stage == STAGE, import_jobs.c.state == "queued").order_by(import_jobs.c.queued_at)).all()]
    done = failed = 0
    for jid in ids:
        with engine.begin() as conn:
            job = conn.execute(select(import_jobs).where(import_jobs.c.id == jid)).one()
            if job.state != "queued":
                continue
            conn.execute(update(import_jobs).where(import_jobs.c.id == jid).values(state="running", started_at=now, error_key=None))
        error: str | None = None
        try:
            with engine.begin() as conn:
                p = job.params or {}
                validate_dataset(conn, store, job.dataset_id, p["column_map"], set(known_variants), job.requested_by or "system", limits, mapping_id=p.get("mapping_id"), now=now, record_job=False)
        except (SeedFileError, LifecycleError) as exc:
            error = exc.code
        except Exception:
            error = "import_failed"
        if error:
            log.error("IMPORT_FAILED job=%s reason=%s", jid, error)                      # a stable code only: never file content or names
        with engine.begin() as conn:
            conn.execute(update(import_jobs).where(import_jobs.c.id == jid).values(state="failed" if error else "done", finished_at=datetime.now(UTC), error_key=error))
        done, failed = done + (error is None), failed + (error is not None)
    return {"processed": len(ids), "done": done, "failed": failed}


def list_jobs(conn: Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(select(import_jobs, seed_datasets.c.version, seed_datasets.c.name, seed_datasets.c.row_count).join(seed_datasets, seed_datasets.c.id == import_jobs.c.dataset_id)
                        .order_by(import_jobs.c.queued_at.desc().nullslast(), import_jobs.c.started_at.desc().nullslast()).limit(min(limit, 200))).all()
    iso = lambda d: None if d is None else d.isoformat()  # noqa: E731
    return [{"id": r.id, "dataset_id": r.dataset_id, "version": r.version, "name": r.name, "rows": r.row_count, "stage": r.stage, "state": r.state, "queued_at": iso(r.queued_at),
             "started_at": iso(r.started_at), "finished_at": iso(r.finished_at), "error_key": r.error_key, "requested_by": r.requested_by} for r in rows]
