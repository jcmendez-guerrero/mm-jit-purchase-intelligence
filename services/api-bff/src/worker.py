"""Role-mirror relay (US1): sends queued role changes to procurement, with bounded retries and visible failures.

    python -m worker          one pass (a short cron job, scale to zero); MMI_WORKER_LOOP_SECONDS keeps it looping locally

The request that changes a role also tries one pass straight away, so the normal path needs no running worker; this job
only retries what failed. Procurement applies a change only if its revision is newer, so retries can never roll roles back.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import Any, Protocol

from db.roles import RoleStore

log = logging.getLogger("api_bff.worker")
MAX_ATTEMPTS = 8


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
    return {"considered": len(due), "sent": sent, "failed_attempts": failed}


def main() -> int:
    from clients.procurement import RoleMirrorClient
    from db.engine import make_engine
    from mmi_common.logging import configure_logging
    from mmi_common.workerloop import run

    configure_logging()
    store = RoleStore(make_engine())
    client = RoleMirrorClient()

    def once() -> int:
        stats = drain_once(store, client)
        log.info("role mirror pass %s", stats)
        return 0 if stats["failed_attempts"] == 0 else 1

    return run(once)


if __name__ == "__main__":
    sys.exit(main())
