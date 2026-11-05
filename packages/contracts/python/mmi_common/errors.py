"""Stable error codes for API responses (FR-028: no user-facing free text in services; the BFF maps codes to es-ES)."""

from __future__ import annotations

import re


def error_code(exc: BaseException) -> str:
    """The exception's own ``code`` when it has one, otherwise a snake_case name derived from its class."""
    code = getattr(exc, "code", None)
    if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_:]*", code):
        return code
    name = type(exc).__name__.removesuffix("Error")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower() or "error"
