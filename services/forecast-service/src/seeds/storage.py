"""T107: file checks before a single row is read, the checksum, and the private blob.

A file is refused when it is too big, when its name and its bytes disagree, when it carries a macro, or when it would expand beyond
the decompression limit. Refusals carry stable codes; nothing is stored for a refused file.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from typing import Protocol

from upload_settings import ParseLimits

ZIP_MAGIC = b"PK\x03\x04"
MAX_RATIO = 200                                   # a legitimate sheet compresses far less than this


class SeedFileError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class BlobWriter(Protocol):
    def put(self, name: str, data: bytes) -> str: ...


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_format(filename: str, data: bytes, limits: ParseLimits) -> str:
    """Returns ``csv`` or ``xlsx`` or raises. The extension must agree with the bytes."""
    if len(data) > limits.max_bytes:
        raise SeedFileError("import_file_too_large")
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in ("xlsm", "xlsb", "xls", "xltm", "xlam"):
        raise SeedFileError("import_type_not_allowed", "macro-capable or legacy workbook")
    if ext == "xlsx":
        if not data.startswith(ZIP_MAGIC):
            raise SeedFileError("import_type_not_allowed", "not a workbook")
        _check_zip(data, limits)
        return "xlsx"
    if ext in ("csv", "txt"):
        if data.startswith(ZIP_MAGIC) or b"\x00" in data[:4096]:
            raise SeedFileError("import_type_not_allowed", "binary content in a text file")
        return "csv"
    raise SeedFileError("import_type_not_allowed", "unsupported type")


def _check_zip(data: bytes, limits: ParseLimits) -> None:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        infos = z.infolist()
    except zipfile.BadZipFile as exc:
        raise SeedFileError("import_type_not_allowed", "damaged package") from exc
    names = [i.filename.lower() for i in infos]
    if any(n.endswith("vbaproject.bin") or n.startswith("xl/macrosheets") or (n.endswith(".bin") and "vba" in n) for n in names) or "xl/workbook.xml" not in names:
        raise SeedFileError("import_type_not_allowed", "macro part or not a workbook")
    if any(n.startswith("xl/externallinks/") for n in names):
        raise SeedFileError("import_type_not_allowed", "external links")                     # a workbook must not pull data from another file
    total = sum(i.file_size for i in infos)
    if total > limits.max_decompressed_bytes or any(i.compress_size and i.file_size / i.compress_size > MAX_RATIO and i.file_size > 1024 * 1024 for i in infos):
        raise SeedFileError("import_decompression_limit")


def store_private(writer: BlobWriter, dataset_id: str, filename: str, data: bytes) -> str:
    """The original file goes to the private container (never a public URL); the caller keeps only the reference."""
    safe = "".join(c for c in filename if c.isalnum() or c in "._-")[:80] or "seed"
    return writer.put(f"seeds/{dataset_id}/{safe}", data)
