"""Forecast worker (T146/T148): drains forecast-in (running a forecast per demand update), then relays the outbox.

    python -m worker          one pass (ACA job on a short cron, scale to zero); `python -m job` remains for a manual run
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from db.tables import outbox
from mmi_common.busfactory import bus_from_env
from mmi_common.logging import configure_logging
from mmi_common.outbox import relay_once
from mmi_common.servicetoken import service_token
from mmi_common.workerloop import run as run_loop
from runs.consumer import consume_once
from runs.runner import SUBSCRIPTIONS
from runs.sources import InventoryHttpSource, LocalBlobWriter
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

log = logging.getLogger("forecast.worker")


def run_once(engine: Engine, bus, blobs, source, writer) -> dict[str, int]:  # type: ignore[no-untyped-def]
    stats = consume_once(engine, bus, blobs, source, writer)
    with engine.begin() as conn:
        sent = relay_once(conn, outbox, bus, SUBSCRIPTIONS)
    return {"applied": stats.applied, "duplicates": stats.duplicates, "rejected": stats.rejected, "failed": stats.failed, "relayed": sent}


class FileBlobs:
    def get(self, uri: str) -> bytes:
        return Path(uri.removeprefix("file://")).read_bytes()


def token_for(audience: str, subject: str, static_var: str):  # type: ignore[no-untyped-def]
    """A static token from the environment (tests, manual runs) or a fresh one from the issuer / managed identity on every call."""
    if static := os.environ.get(static_var):
        return static
    return lambda: service_token(audience, subject, ["viewer"])


def main() -> int:
    configure_logging()
    try:
        engine = create_engine(os.environ["MMI_DATABASE_URL"])
        source = InventoryHttpSource(os.environ["MMI_INVENTORY_URL"], token_for("api://mmi-inventory-service", "svc-forecast", "MMI_INVENTORY_TOKEN"))
        writer = LocalBlobWriter(Path(os.environ.get("MMI_BLOB_ROOT", "/tmp/mmi-forecast")))  # noqa: S108 - local default only
        result = run_once(engine, bus_from_env(), FileBlobs(), source, writer)
    except Exception:
        log.exception("WORKER_FAILED")
        return 1
    log.info("forecast worker pass: %s", result)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(run_loop(main))
