"""Full-list reference syncs: warehouses, products, variants (the variants list carries stock totals).

Each run reads the whole list, reconciles the distinct row count with the total Siweb reports, writes the
stripped raw payload and announces it through the outbox. Products that disappear are not deleted here:
inventory-service tombstones them only after N consecutive missed syncs, so a single failed run never does.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from client.reader import AuthExpiredError, BudgetExhaustedError, ReaderClient, siweb_total
from db.tables import raw_payload_index, sync_runs
from mmi_common.time import get_correlation_id, set_correlation_id
from outbox.publisher import publish_sync_completed
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from storage.blob import BlobStore

from sync.raw_store import DEFAULT_RETENTION_DAYS, write_raw
from sync.runner import RunResult

PATHS = {
    "warehouses": "/api/public/inventory/warehouses",
    "products": "/api/public/inventory/products",
    "variants": "/api/public/inventory/variants",
}


@dataclass
class SnapshotSync:
    reader: ReaderClient
    engine: Engine
    store: BlobStore
    kind: str
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    retention_days: int = DEFAULT_RETENTION_DAYS

    def run(self) -> RunResult:
        now, cid, run_id = self.clock(), get_correlation_id() or set_correlation_id(), str(uuid.uuid4())
        start_requests = self.reader.requests_made
        rows: dict[int, dict[str, Any]] = {}
        total: int | None = None
        complete, auth_failed = False, False
        try:
            for _, body, page in self.reader.pages(PATHS[self.kind]):
                total = siweb_total(body) if total is None else total
                for r in page:
                    rows.setdefault(int(r["id"]), r)
            complete = True
        except BudgetExhaustedError:
            pass
        except AuthExpiredError:
            auth_failed = True
        reconciled = complete and (total is None or len(rows) == total)  # warehouses list reports no total
        status = "failed" if auth_failed else ("committed" if complete else "partial")
        res = RunResult(run_id, status, fetched=len(rows), stored=len(rows), siweb_total=total, reconciled=reconciled,
                        requests_used=self.reader.requests_made - start_requests, record_ids=sorted(rows))
        with self.engine.begin() as conn:
            conn.execute(insert(sync_runs).values(
                id=run_id, kind=self.kind, status=status, started_at=now, finished_at=self.clock(), counts_fetched=res.fetched,
                counts_stored=res.stored, counts_errors=0, siweb_total=total, reconciled=reconciled, requests_used=res.requests_used))
            if complete:  # a partial list must not look like a full snapshot, so nothing is announced
                doc = {"run_id": run_id, "kind": self.kind, "reconciled": reconciled, "counts_stored": res.stored,
                       "records": [rows[i] for i in sorted(rows)]}
                raw = write_raw(self.store, self.kind, run_id, doc, now, self.retention_days)
                conn.execute(insert(raw_payload_index).values(
                    blob_uri=raw.uri, run_id=run_id, sha256=raw.sha256, fetched_at=now, expires_at=raw.expires_at))
                publish_sync_completed(conn, run_id, raw, cid)
        if auth_failed:
            raise AuthExpiredError("token rejected; run stopped")
        return res
