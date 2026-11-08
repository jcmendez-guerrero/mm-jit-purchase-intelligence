"""T012: file checks before a single row is read. Same rules as the seed import, without importing service code.

Refusals carry stable codes (contracts/local-loader.md). Limits come from the same ``MMI_UPLOAD_*`` variables as the BFF.
"""

from __future__ import annotations

import io
import os
import re
import zipfile
from dataclasses import dataclass

from . import formats

MIB = 1024 * 1024
ZIP_MAGIC = b"PK\x03\x04"
MAX_RATIO = 200


class LoaderFileError(Exception):
    def __init__(self, code: str, message: str = "", missing: list[str] | None = None, unexpected: list[str] | None = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.missing = missing or []
        self.unexpected = unexpected or []


@dataclass(frozen=True)
class Limits:
    max_bytes: int = 5 * MIB
    max_rows: int = 100_000
    max_decompressed_bytes: int = 100 * MIB


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw and raw.isdigit() and int(raw) > 0 else default


def load_limits() -> Limits:
    return Limits(
        max_bytes=min(_int_env("MMI_UPLOAD_MAX_BYTES", 5 * MIB), 25 * MIB),
        max_rows=_int_env("MMI_UPLOAD_MAX_ROWS", 100_000),
        max_decompressed_bytes=_int_env("MMI_UPLOAD_MAX_DECOMPRESSED_BYTES", 100 * MIB),
    )


def detect_format(filename: str, data: bytes, limits: Limits) -> str:
    """Returns ``csv`` or ``xlsx``; the extension must agree with the bytes."""
    if len(data) > limits.max_bytes:
        raise LoaderFileError("local_load_file_too_large")
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "xlsx":
        if not data.startswith(ZIP_MAGIC):
            raise LoaderFileError("local_load_type_not_allowed", "not a workbook")
        _check_package(data, limits)
        return "xlsx"
    if ext in ("csv", "txt"):
        if data.startswith(ZIP_MAGIC) or b"\x00" in data[:4096]:
            raise LoaderFileError("local_load_type_not_allowed", "binary content in a text file")
        return "csv"
    raise LoaderFileError("local_load_type_not_allowed", "unsupported or macro-capable type")


def _check_package(data: bytes, limits: Limits) -> None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except zipfile.BadZipFile as exc:
        raise LoaderFileError("local_load_type_not_allowed", "damaged package") from exc
    names = [i.filename.lower() for i in infos]
    if "xl/workbook.xml" not in names:
        raise LoaderFileError("local_load_type_not_allowed", "not a workbook")
    if any(n.endswith("vbaproject.bin") or n.startswith("xl/macrosheets") or n.startswith("xl/externallinks/") for n in names):
        raise LoaderFileError("local_load_macros_or_links", "macro part or external link")
    total = sum(i.file_size for i in infos)
    if total > limits.max_decompressed_bytes or any(i.compress_size and i.file_size / i.compress_size > MAX_RATIO and i.file_size > MIB for i in infos):
        raise LoaderFileError("local_load_file_too_large", "decompression limit")
    for info in infos:
        if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", info.filename.lower()):
            xml = zf.read(info.filename)
            if re.search(rb"<(?:\w+:)?f[\s>/]", xml):
                raise LoaderFileError("local_load_macros_or_links", "formula cell")


def check_row_count(rows: int, limits: Limits) -> None:
    if rows > limits.max_rows:
        raise LoaderFileError("local_load_too_many_rows")


def normalise_headers(headers: list[str]) -> list[str]:
    return [h.replace("﻿", "").strip() for h in headers]


def check_headers(kind: str, headers: list[str]) -> None:
    """Every column of the layout must be present; the message lists what is missing and unexpected."""
    got = normalise_headers(headers)
    want = formats.HEADERS[kind]
    missing = [h for h in want if h not in got]
    unexpected = [h for h in got if h and h not in want]
    if missing:
        raise LoaderFileError(
            "local_load_signature_mismatch",
            f"Faltan columnas: {', '.join(missing)}" + (f". Columnas inesperadas: {', '.join(unexpected)}" if unexpected else ""),
            missing=missing, unexpected=unexpected,
        )
