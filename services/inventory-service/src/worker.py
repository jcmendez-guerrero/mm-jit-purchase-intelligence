"""Inventory worker (T146/T148): drains inventory-in through the pipeline, then relays the outbox. Run on a short schedule.

    python -m worker          one pass, exit code 0 (ACA job on a cron, scale to zero)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from db.tables import outbox
from demand.pipeline import Pipeline
from demand.publisher import SUBSCRIPTIONS, LocalBlobWriter
from mmi_common.busfactory import bus_from_env
from mmi_common.logging import configure_logging
from mmi_common.outbox import relay_once
from mmi_common.time import get_correlation_id, set_correlation_id
from mmi_common.workerloop import run as run_loop
from projections.blob import LocalBlobReader
from projections.consumer import consume_once
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

log = logging.getLogger("inventory.worker")


def run_once(engine: Engine, bus, blobs, writer, correlation_id: str | None = None) -> dict[str, int]:  # type: ignore[no-untyped-def]
    stats = consume_once(engine, bus, blobs, pipeline=Pipeline(writer, correlation_id or get_correlation_id() or set_correlation_id()))
    with engine.begin() as conn:
        sent = relay_once(conn, outbox, bus, SUBSCRIPTIONS)
    return {"applied": stats.applied, "duplicates": stats.duplicates, "rejected": stats.rejected, "failed": stats.failed, "relayed": sent}


def main() -> int:
    configure_logging()
    try:
        engine = create_engine(os.environ["MMI_DATABASE_URL"])
        writer = LocalBlobWriter(Path(os.environ.get("MMI_BLOB_ROOT", "/tmp/mmi-inventory")))  # noqa: S108 - local default only
        result = run_once(engine, bus_from_env(), LocalBlobReader(), writer)
    except Exception:
        log.exception("WORKER_FAILED")
        return 1
    log.info("inventory worker pass: %s", result)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(run_loop(main))
