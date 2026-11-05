"""Role-based access control (RBAC) and request guards (T110).

Allowed roles: viewer, buyer, approver, admin.
- viewer: read-only access (GET endpoints).
- buyer: create and edit proposals, manage supplier terms, import price lists, review data quality.
- approver: approve proposals (separation of duties enforced).
- admin: manage user roles and global configuration.

Unauthorized access attempts are logged and refused with 401 or 403.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from auth.csrf import validate_csrf
from auth.session import SessionData, get_current_session
from fastapi import Depends, HTTPException, Request

logger = logging.getLogger("mmi.api_bff.rbac")

VALID_ROLES = {"viewer", "buyer", "approver", "admin"}

# In-memory refusal log for auditing and assertions
_refusal_log: list[dict[str, Any]] = []


def get_refusal_log() -> list[dict[str, Any]]:
    return list(_refusal_log)


def clear_refusal_log() -> None:
    _refusal_log.clear()


def log_refusal(request: Request, user_id: str | None, roles: list[str], required_roles: list[str], reason: str) -> None:
    entry = {
        "path": request.url.path,
        "method": request.method,
        "user_id": user_id,
        "roles": roles,
        "required_roles": required_roles,
        "reason": reason,
    }
    _refusal_log.append(entry)
    logger.warning("Access refused: %s", entry)


def require_session(request: Request) -> SessionData:
    session = get_current_session(request)
    if not session:
        log_refusal(request, None, [], [], "unauthenticated")
        raise HTTPException(status_code=401, detail="unauthenticated")
    # Enforce CSRF check on mutating requests
    validate_csrf(request, session)
    return session


def require_roles(*allowed_roles: str) -> Callable[[Request, SessionData], SessionData]:
    required = list(allowed_roles)

    def dependency(request: Request, session: SessionData = Depends(require_session)) -> SessionData:
        user_roles = set(session.roles)
        if not user_roles.intersection(required):
            log_refusal(request, session.user_id, session.roles, required, "forbidden_missing_role")
            raise HTTPException(status_code=403, detail="forbidden: insufficient permissions")
        return session

    return dependency


def require_fresh_mfa(max_age_seconds: int = 300) -> Callable[[Request, SessionData], SessionData]:
    def dependency(request: Request, session: SessionData = Depends(require_session)) -> SessionData:
        if not session.is_mfa_fresh(max_age_seconds=max_age_seconds):
            log_refusal(request, session.user_id, session.roles, [], "forbidden_mfa_stale")
            raise HTTPException(status_code=403, detail="fresh MFA authentication required")
        return session

    return dependency
