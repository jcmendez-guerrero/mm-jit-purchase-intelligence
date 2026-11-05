"""Forecast job entrypoint (T069): one invocation = one forecast run, started after inventory.demand.updated.v1.

    python -m job

Environment: MMI_DATABASE_URL, MMI_INVENTORY_URL, MMI_INVENTORY_TOKEN (dev) and MMI_BLOB_ROOT (local) or the Azure
account settings. Exit code 0 on success or when an identical run already exists, 1 on failure.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from mmi_common.logging import configure_logging
from runs.runner import run_forecast
from runs.sources import InventoryHttpSource, LocalBlobWriter
from sqlalchemy import create_engine

log = logging.getLogger("forecast-service.job")


def main() -> int:
    configure_logging()
    try:
        engine = create_engine(os.environ["MMI_DATABASE_URL"])
        source = InventoryHttpSource(os.environ["MMI_INVENTORY_URL"], os.environ["MMI_INVENTORY_TOKEN"])
        writer = LocalBlobWriter(Path(os.environ.get("MMI_BLOB_ROOT", "/tmp/mmi-forecast")))  # noqa: S108 - local default only
        result = run_forecast(engine, source, writer)
    except Exception:
        log.exception("FORECAST_FAILED")
        return 1
    log.info("FORECAST_OK run=%s reused=%s total=%s eligible=%s adopted=%s", result.run_id, result.reused, result.total, result.eligible, result.adopted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
