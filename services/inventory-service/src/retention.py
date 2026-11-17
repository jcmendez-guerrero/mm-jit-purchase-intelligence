"""Retention job (T066, feature 018): removes quality records older than five years. Run on a schedule, scale to zero.

    python -m retention          one pass, exit code 0
"""

from __future__ import annotations

import logging
import os
import sys

from mmi_common.logging import configure_logging
from quality.retention import purge
from sqlalchemy import create_engine

log = logging.getLogger("inventory.retention")


def main() -> int:
    configure_logging()
    try:
        with create_engine(os.environ["MMI_DATABASE_URL"]).begin() as conn:
            counts = purge(conn)
    except Exception:
        log.exception("RETENTION_FAILED")
        return 1
    log.info("retention pass: %s", counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
