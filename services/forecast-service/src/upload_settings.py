"""Parsing limits for seed files (T002). A file that exceeds any limit is refused before its rows are read."""

from __future__ import annotations

import os
from dataclasses import dataclass

MIB = 1024 * 1024


@dataclass(frozen=True)
class ParseLimits:
    max_bytes: int = 5 * MIB
    max_decompressed_bytes: int = 50 * MIB
    max_rows: int = 50_000
    max_columns: int = 30
    max_sheets: int = 5


def load_limits() -> ParseLimits:
    raw = os.environ.get("MMI_UPLOAD_MAX_BYTES")
    if raw and raw.isdigit() and int(raw) > 0:
        return ParseLimits(max_bytes=min(int(raw), 25 * MIB))
    return ParseLimits()
