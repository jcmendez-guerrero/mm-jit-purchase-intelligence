"""The authenticated user of the current request, available to the downstream clients.

Procurement judges "who created / who approves" and "is the second factor fresh" from the token it receives, so the BFF must
forward the real user, never a shared service identity. A ContextVar set by middleware carries it into async client calls.
"""

from __future__ import annotations

from contextvars import ContextVar

from .session import SessionData

current_identity: ContextVar[SessionData | None] = ContextVar("current_identity", default=None)
