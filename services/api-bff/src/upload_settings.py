"""Upload limits for the predictive seed import (T002). Defaults are conservative and configurable by environment."""

from __future__ import annotations

import os
from dataclasses import dataclass

MIB = 1024 * 1024


@dataclass(frozen=True)
class UploadLimits:
    max_bytes: int = 5 * MIB
    allowed_extensions: tuple[str, ...] = (".csv", ".xlsx")
    allowed_content_types: tuple[str, ...] = (
        "text/csv",
        "application/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    )


def load_limits() -> UploadLimits:
    raw = os.environ.get("MMI_UPLOAD_MAX_BYTES")
    max_bytes = int(raw) if raw and raw.isdigit() and int(raw) > 0 else UploadLimits.max_bytes
    return UploadLimits(max_bytes=min(max_bytes, 25 * MIB))
