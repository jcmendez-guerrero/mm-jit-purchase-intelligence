"""CSRF validation for mutating endpoints (T109).

Mutating requests (POST, PUT, DELETE, PATCH) must provide the X-CSRF-Token header matching
the CSRF token stored in the user's secure cookie session.
"""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request

from .session import SessionData

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def validate_csrf(request: Request, session: SessionData) -> None:
    if request.method in SAFE_METHODS:
        return
    token = request.headers.get("X-CSRF-Token")
    if not token or not hmac.compare_digest(token, session.csrf_token):
        raise HTTPException(status_code=403, detail="auth_csrf_invalid")
