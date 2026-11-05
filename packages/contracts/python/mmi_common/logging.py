"""Structured JSON logging with correlation ID and redaction of secrets and personal data."""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

from .time import get_correlation_id

REDACTED = "[REDACTED]"
SENSITIVE_KEYS = re.compile(
    r"(authorization|token|secret|password|passwd|api[_-]?key|cookie|cif|notes?|email|connection[_-]?string)",
    re.IGNORECASE,
)
BEARER = re.compile(r"(?i)bearer\s+[a-z0-9\-_\.=]+")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def redact(value: Any, key: str | None = None) -> Any:
    if key is not None and SENSITIVE_KEYS.search(key):
        return REDACTED
    if isinstance(value, dict):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return EMAIL.sub(REDACTED, BEARER.sub(f"Bearer {REDACTED}", value))
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "correlation_id": get_correlation_id(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload.update(redact(extra))
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO, stream: Any = None) -> None:
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for noisy in ("azure", "httpx", "httpcore", "urllib3"):     # per-request transport logs bury the markers the alerts query
        logging.getLogger(noisy).setLevel(logging.WARNING)
