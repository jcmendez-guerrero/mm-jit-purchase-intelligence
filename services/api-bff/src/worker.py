"""Role-mirror relay (US1): sends queued role changes to procurement, with bounded retries and visible failures.

    python -m worker          one pass (a short cron job, scale to zero); MMI_WORKER_LOOP_SECONDS keeps it looping locally

The request that changes a role also tries one pass straight away, so the normal path needs no running worker; this job
only retries what failed. Procurement applies a change only if its revision is newer, so retries can never roll roles back.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from db.ops import OpsStore
from db.roles import RoleStore
from ops.snapshots import SnapshotError, parse_snapshot

log = logging.getLogger("api_bff.worker")
MAX_ATTEMPTS = 8
LAG_ALERT_SECONDS = 900                  # the alert rule watches for ROLE_MIRROR_LAG; a change older than this has not reached procurement


class RoleMirror(Protocol):
    def put_user_roles(self, user_id: str, roles: list[str], active: bool, revision: int) -> None: ...


def drain_once(store: RoleStore, client: RoleMirror, now: datetime | None = None, max_attempts: int = MAX_ATTEMPTS, limit: int = 100) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    due = store.due_mirrors(now, limit)
    sent = failed = 0
    for row in due:
        try:
            client.put_user_roles(row.user_id, list(row.roles_snapshot), bool(row.active), int(row.revision))
        except Exception as exc:                      # any failure is retried and shown to the admin; the cause is logged, not stored
            log.warning("ROLE_MIRROR_FAILED user=%s reason=%s", row.user_id, type(exc).__name__)
            store.mark_attempt_failed(row.id, now, "role_mirror_failed", max_attempts)
            failed += 1
        else:
            store.mark_sent(row.id, now)
            sent += 1
    lag = store.mirror_status(now)
    if lag["oldest_pending_seconds"] > LAG_ALERT_SECONDS or lag["failed"] > 0:
        log.error("ROLE_MIRROR_LAG seconds=%d pending=%d failed=%d", lag["oldest_pending_seconds"], lag["pending"], lag["failed"])
    return {"considered": len(due), "sent": sent, "failed_attempts": failed}


SNAPSHOT_DIR = "ops-inputs"                 # gitignored; written by an operator command or a scheduled pipeline step (D10)


def ingest_snapshots(ops: OpsStore, directory: Path, now: datetime | None = None) -> dict[str, int]:
    """Reads *.json snapshots; a file that fails validation is refused and logged by code only, never stored. Re-reading is harmless."""
    stored = rejected = 0
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            snap = parse_snapshot(raw, now)
            if ops.add_snapshot(snap.kind, snap.captured_at, str(raw["captured_at"]), snap.payload(), snap.status):
                stored += 1
        except (SnapshotError, ValueError, OSError, KeyError, TypeError) as exc:
            log.warning("SNAPSHOT_REJECTED file=%s code=snapshot_invalid reason=%s", path.name[:60], type(exc).__name__)
            rejected += 1
    return {"stored": stored, "rejected": rejected}


def store_snapshot_file(ops: OpsStore, path: Path, now: datetime | None = None) -> int:
    """`python -m worker snapshot <file>`: validates and stores one snapshot. Exit 0 stored or already stored, 1 refused (code only is logged)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        snap = parse_snapshot(raw, now)
        stored = ops.add_snapshot(snap.kind, snap.captured_at, str(raw["captured_at"]), snap.payload(), snap.status)
    except (SnapshotError, ValueError, OSError, KeyError, TypeError) as exc:
        log.error("SNAPSHOT_REJECTED file=%s code=snapshot_invalid reason=%s", path.name[:60], type(exc).__name__)
        return 1
    log.info("snapshot %s %s", snap.kind, "stored" if stored else "already stored")
    return 0


def main() -> int:
    from clients.procurement import RoleMirrorClient
    from db.engine import make_engine
    from mmi_common.logging import configure_logging
    from mmi_common.workerloop import run

    configure_logging()
    if len(sys.argv) == 3 and sys.argv[1] == "snapshot":          # operator command: no mirror pass, no loop
        return store_snapshot_file(OpsStore(make_engine()), Path(sys.argv[2]))
    store = RoleStore(make_engine())
    client = RoleMirrorClient()

    def once() -> int:
        import asyncio

        from clients.forecast import ForecastClient
        from clients.inventory import InventoryClient
        from routes import admin_roles
        from routes.admin_ops import get_ops, refresh_all

        stats = drain_once(store, client)
        log.info("role mirror pass %s", stats)
        admin_roles.set_store(store)
        ops = get_ops()
        log.info("snapshot pass %s", ingest_snapshots(ops, Path(os.environ.get("MMI_OPS_INPUT_DIR", SNAPSHOT_DIR))))
        # Complete evaluation, so stale sources and failed jobs raise their alert (and e-mail marker) without anyone opening the console.
        # Read-only: the BFF service identity asks for the viewer role only.
        asyncio.run(refresh_all(ops, InventoryClient(), ForecastClient(), {"user_id": "svc-api-bff", "roles": ["viewer"]}, datetime.now(UTC)))
        return 0 if stats["failed_attempts"] == 0 else 1

    return run(once)


if __name__ == "__main__":
    sys.exit(main())
