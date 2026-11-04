"""Movement sync orchestration (T038).

* ``date_to`` is frozen per window to yesterday (Europe/Madrid) so newest-first paging cannot shift mid-run.
  A multi-night backfill keeps the same frozen window through ``sync_checkpoints.backfill_cursor``.
* Rows are deduplicated by movement ``id``; rows at or below the checkpoint are counted as already known.
* Counts are reconciled against the total Siweb reports: distinct rows processed must equal ``siweb_total``.
* One transaction commits run, errors, raw index, checkpoint and outbox event together. The checkpoint only
  advances when the whole window is done; a spent budget saves the cursor and resumes next night.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from client.reader import AuthExpiredError, BudgetExhaustedError, ReaderClient, siweb_total
from db.tables import import_errors, raw_payload_index, sync_checkpoints, sync_runs
from mapping.quality import check_movement
from mmi_common.time import ASSUMED_LOCAL_TZ, get_correlation_id, parse_siweb_timestamp, set_correlation_id
from outbox.publisher import publish_sync_completed
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine
from storage.blob import BlobStore

from sync.raw_store import DEFAULT_RETENTION_DAYS, write_raw

MOVEMENTS = "movements"
MOVEMENTS_PATH = "/api/public/inventory/movements"


@dataclass
class RunResult:
    run_id: str
    status: str  # committed / partial / failed
    fetched: int = 0
    stored: int = 0
    errors: int = 0
    known: int = 0
    siweb_total: int | None = None
    reconciled: bool = False
    requests_used: int = 0
    record_ids: list[int] = field(default_factory=list)


def _aware(dt: datetime | None) -> datetime | None:
    return None if dt is None else (dt if dt.tzinfo else dt.replace(tzinfo=UTC))


@dataclass
class MovementSync:
    reader: ReaderClient
    engine: Engine
    store: BlobStore
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    retention_days: int = DEFAULT_RETENTION_DAYS
    page_size: int = 200

    def run(self) -> RunResult:
        now = self.clock()
        cid = get_correlation_id() or set_correlation_id()
        run_id = str(uuid.uuid4())
        with self.engine.begin() as conn:
            cp = conn.execute(select(sync_checkpoints).where(sync_checkpoints.c.kind == MOVEMENTS)).first()
            last_id = cp.last_movement_id if cp and cp.last_movement_id is not None else None
            cursor: dict[str, Any] | None = cp.backfill_cursor if cp else None
            if cursor:
                date_to, date_from = cursor["date_to"], cursor.get("date_from")
                next_page, processed, total = cursor["next_page"], cursor["processed"], cursor.get("siweb_total")
            else:
                local_today = now.astimezone(ZoneInfo(ASSUMED_LOCAL_TZ)).date()
                date_to = (local_today - timedelta(days=1)).isoformat()
                date_from = None
                if cp and cp.last_created_at is not None:
                    date_from = _aware(cp.last_created_at).astimezone(ZoneInfo(ASSUMED_LOCAL_TZ)).date().isoformat()
                next_page, processed, total = 1, 0, None
            conn.execute(insert(sync_runs).values(
                id=run_id, kind=MOVEMENTS, frozen_date_to=date_to, status="running", started_at=now,
                counts_fetched=0, counts_stored=0, counts_errors=0, reconciled=False, requests_used=0))

        params: dict[str, Any] = {"date_to": date_to, **({"date_from": date_from} if date_from else {})}
        res = RunResult(run_id, "running")
        seen: set[int] = set()
        records: list[dict[str, Any]] = []
        quarantined: dict[int, list[str]] = {}
        issues: list[tuple[str, str, str, str, bool]] = []
        start_requests = self.reader.requests_made
        finished_pages = False
        auth_failed = False
        page = next_page
        try:
            for page, body, rows in self.reader.pages(MOVEMENTS_PATH, params, self.page_size, next_page):
                total = siweb_total(body) if total is None else total
                for raw in rows:
                    rid = int(raw["id"])
                    if rid in seen:  # a page shifted: dedupe by id
                        continue
                    seen.add(rid)
                    if last_id is not None and rid <= last_id:
                        res.known += 1
                        continue
                    records.append(raw)
                    check = check_movement(raw)
                    for i in check.issues:
                        issues.append((i.entity, i.external_id, i.code, i.detail, i.blocking))
                    if check.movement is not None:
                        res.stored += 1
                    else:
                        res.errors += 1
                        quarantined[rid] = [i.code for i in check.issues if i.blocking]
                next_page = page + 1
            finished_pages = True
        except BudgetExhaustedError:
            pass
        except AuthExpiredError:
            auth_failed = True

        res.fetched = len(seen)
        res.requests_used = self.reader.requests_made - start_requests
        res.siweb_total = total
        res.record_ids = [int(r["id"]) for r in records]
        done = finished_pages
        res.reconciled = bool(done and total is not None and processed + res.fetched == total)
        res.status = "failed" if auth_failed else ("committed" if done else "partial")

        with self.engine.begin() as conn:
            raw_payload = None
            if records and not auth_failed:
                document = {"run_id": run_id, "kind": MOVEMENTS, "window": {"date_from": date_from, "date_to": date_to},
                            "reconciled": res.reconciled, "counts_stored": res.stored, "records": records,
                            "quarantined": {str(k): v for k, v in quarantined.items()}}
                raw_payload = write_raw(self.store, MOVEMENTS, run_id, document, now, self.retention_days)
                conn.execute(insert(raw_payload_index).values(
                    blob_uri=raw_payload.uri, run_id=run_id, sha256=raw_payload.sha256, fetched_at=now, expires_at=raw_payload.expires_at))
                publish_sync_completed(conn, run_id, raw_payload, cid)
            self._record_issues(conn, run_id, issues)
            if not auth_failed:
                self._save_checkpoint(conn, cp is not None, last_id, done, {
                    "date_to": date_to, "date_from": date_from, "next_page": next_page,
                    "processed": processed + res.fetched, "siweb_total": total, **self._newest(cursor, records)})
            conn.execute(update(sync_runs).where(sync_runs.c.id == run_id).values(
                status=res.status, counts_fetched=res.fetched, counts_stored=res.stored, counts_errors=res.errors,
                siweb_total=total, reconciled=res.reconciled, requests_used=res.requests_used,
                finished_at=self.clock()))
        if auth_failed:
            raise AuthExpiredError("token rejected; run stopped")
        return res

    @staticmethod
    def _newest(cursor: dict[str, Any] | None, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Newest movement seen across every night of a backfill (the checkpoint must not take only the last batch)."""
        best = {"max_id": (cursor or {}).get("max_id"), "max_created_at": (cursor or {}).get("max_created_at")}
        for r in records:
            if best["max_id"] is None or int(r["id"]) > best["max_id"]:
                best = {"max_id": int(r["id"]), "max_created_at": r["created_at"]}
        return best

    @staticmethod
    def _record_issues(conn: Connection, run_id: str, issues: list[tuple[str, str, str, str, bool]]) -> None:
        for entity, ext, code, detail, blocking in issues:
            exists = conn.execute(select(import_errors.c.id).where(
                (import_errors.c.entity == entity) & (import_errors.c.external_id == ext) & (import_errors.c.error_code == code))).first()
            if not exists:  # a resolved or ignored decision is never reopened by a re-sync
                conn.execute(insert(import_errors).values(
                    run_id=run_id, entity=entity, external_id=ext, error_code=code, detail=detail[:200],
                    blocking=blocking, status="open"))

    @staticmethod
    def _save_checkpoint(conn: Connection, exists: bool, last_id: int | None, done: bool, cursor: dict[str, Any]) -> None:
        values: dict[str, Any]
        if done:
            values = {"backfill_cursor": None}
            max_id = cursor.get("max_id")
            if max_id is not None and (last_id is None or max_id > last_id):
                values.update(last_movement_id=max_id, last_created_at=parse_siweb_timestamp(cursor["max_created_at"]).utc)
        else:
            values = {"backfill_cursor": cursor}
        if exists:
            conn.execute(update(sync_checkpoints).where(sync_checkpoints.c.kind == MOVEMENTS).values(**values))
        else:
            conn.execute(insert(sync_checkpoints).values(kind=MOVEMENTS, **values))


__all__ = ["MOVEMENTS", "MovementSync", "RunResult", "date"]
