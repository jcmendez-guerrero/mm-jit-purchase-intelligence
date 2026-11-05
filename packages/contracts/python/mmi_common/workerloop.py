"""Run a worker pass once, or repeatedly when MMI_WORKER_LOOP_SECONDS is set (the Compose and always-on mode)."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

log = logging.getLogger("mmi.worker")


def run(once: Callable[[], int], sleep: Callable[[float], None] = time.sleep, max_passes: int | None = None) -> int:
    """Exit code of the last pass. A failing pass is logged by the pass itself and the loop carries on, so one bad message
    or a brief outage never stops the worker; the scheduler's alerts see the WORKER_FAILED / POISON_MESSAGE markers."""
    interval = float(os.environ.get("MMI_WORKER_LOOP_SECONDS", "0") or 0)
    code, passes = once(), 1
    while interval > 0 and (max_passes is None or passes < max_passes):
        sleep(interval)
        code = once()
        passes += 1
    return code
