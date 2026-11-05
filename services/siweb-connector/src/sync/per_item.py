"""T149: per-item collections that need one request per variant or product: stock lots and supplier costs.

A full cycle can exceed one night's request budget, so each run works through the items after a persisted cursor and stops
when the budget is spent; the next night continues. Each batch is announced on its own (inventory replaces the lots of the
variants in a batch; procurement ingests the supplier rows). The cycle is reconciled when every item listed at its start was
processed. ``supplier_cif`` and notes are stripped before anything is written.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from client.reader import AuthExpiredError, BudgetExhaustedError, ReaderClient
from db.tables import raw_payload_index, sync_checkpoints, sync_runs
from mmi_common.time import get_correlation_id, set_correlation_id
from outbox.publisher import publish_sync_completed
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine
from storage.blob import BlobStore

from sync.raw_store import DEFAULT_RETENTION_DAYS, write_raw
from sync.runner import RunResult


@dataclass(frozen=True)
class ItemSpec:
    kind: str
    list_path: str
    item_path: str            # contains {id}
    tag: str                  # key added to every row so the consumer knows which item it belongs to


SPECS = {
    "lots": ItemSpec("lots", "/api/public/inventory/variants", "/api/public/inventory/variants/{id}/lots", "variant_id"),
    "supplier_costs": ItemSpec("supplier_costs", "/api/public/inventory/products", "/api/public/inventory/products/{id}/suppliers", "product_id"),
}


@dataclass
class PerItemSync:
    reader: ReaderClient
    engine: Engine
    store: BlobStore
    kind: str
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    retention_days: int = DEFAULT_RETENTION_DAYS
    max_items: int | None = None
    processed_ids: list[int] = field(default_factory=list)

    def run(self) -> RunResult:
        spec = SPECS[self.kind]
        now, cid, run_id = self.clock(), get_correlation_id() or set_correlation_id(), str(uuid.uuid4())
        with self.engine.connect() as conn:
            cp = conn.execute(select(sync_checkpoints).where(sync_checkpoints.c.kind == self.kind)).first()
        cursor: dict[str, Any] = (cp.backfill_cursor if cp and cp.backfill_cursor else {}) or {}
        after, done_before = int(cursor.get("after_id", 0)), int(cursor.get("processed", 0))
        start_requests = self.reader.requests_made
        records: list[dict[str, Any]] = []
        processed: list[int] = []
        auth_failed = cycle_done = False
        ids: list[int] = []
        try:
            ids = sorted({int(r["id"]) for _, _, rows in self.reader.pages(spec.list_path) for r in rows})
            todo = [i for i in ids if i > after]
            batch = todo[: self.max_items] if self.max_items else todo
            for item_id in batch:
                rows = self.reader.get(spec.item_path.format(id=item_id)).get("data") or []
                if rows:
                    records += [{**r, spec.tag: r.get(spec.tag, item_id)} for r in rows]
                elif self.kind == "lots":
                    records.append({spec.tag: item_id, "quantity": 0})      # tells inventory this variant now has no lots
                processed.append(item_id)
            cycle_done = len(processed) == len(todo)
        except BudgetExhaustedError:
            pass                                                            # resume after the last completed item next night
        except AuthExpiredError:
            auth_failed = True
        total = len(ids) if ids else int(cursor.get("total", 0))
        status = "failed" if auth_failed else ("committed" if cycle_done else "partial")
        reconciled = cycle_done and done_before + len(processed) == total
        res = RunResult(run_id, status, fetched=len(processed), stored=len(records), siweb_total=total, reconciled=reconciled,
                        requests_used=self.reader.requests_made - start_requests, record_ids=processed)
        self.processed_ids = processed
        with self.engine.begin() as conn:
            conn.execute(insert(sync_runs).values(
                id=run_id, kind=self.kind, status=status, started_at=now, finished_at=self.clock(), counts_fetched=len(processed), counts_stored=len(records),
                counts_errors=0, siweb_total=total, reconciled=reconciled, requests_used=res.requests_used))
            if processed and not auth_failed:
                doc = {"run_id": run_id, "kind": self.kind, "reconciled": reconciled, "counts_stored": len(records), "records": records}
                raw = write_raw(self.store, self.kind, run_id, doc, now, self.retention_days)
                conn.execute(insert(raw_payload_index).values(blob_uri=raw.uri, run_id=run_id, sha256=raw.sha256, fetched_at=now, expires_at=raw.expires_at))
                publish_sync_completed(conn, run_id, raw, cid)
            if not auth_failed:
                new_cursor = None if cycle_done else {"after_id": processed[-1] if processed else after, "processed": done_before + len(processed), "total": total}
                if cp is None:
                    conn.execute(insert(sync_checkpoints).values(kind=self.kind, backfill_cursor=new_cursor))
                else:
                    conn.execute(update(sync_checkpoints).where(sync_checkpoints.c.kind == self.kind).values(backfill_cursor=new_cursor))
        if auth_failed:
            raise AuthExpiredError("token rejected; run stopped")
        return res
