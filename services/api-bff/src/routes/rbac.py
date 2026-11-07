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
from collections import deque
from collections.abc import Callable
from typing import Any

from auth.csrf import validate_csrf
from auth.session import SessionData, get_current_session
from fastapi import Depends, HTTPException, Request

logger = logging.getLogger("mmi.api_bff.rbac")

VALID_ROLES = {"viewer", "buyer", "approver", "admin"}

# Bounded in-memory view for operations and tests. The durable record of authenticated refusals is the hash-chained audit.
_refusal_log: deque[dict[str, Any]] = deque(maxlen=500)


def get_refusal_log() -> list[dict[str, Any]]:
    return list(_refusal_log)


def effective_roles(session: SessionData) -> list[str] | None:
    """The registry is authoritative for users it knows: a revoked role applies at once even if an old cookie still carries it.
    Returns None for a deactivated user. Users unknown to the registry (identity provider only) keep their session roles."""
    from routes.admin_roles import get_store

    rec = get_store().get(session.user_id)
    if rec is None:
        return list(session.roles)
    return list(rec.roles) if rec.active else None


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
    if user_id:                                           # anonymous refusals are logged only: a flood must not grow the audit table
        try:
            from routes.admin_roles import get_store

            get_store().record_refusal(user_id, "access.refused", f"{request.method} {request.url.path}", after={"reason": reason, "required": required_roles})
        except Exception as exc:
            logger.error("AUDIT_REFUSAL_FAILED reason=%s", type(exc).__name__)


def require_session(request: Request) -> SessionData:
    session = get_current_session(request)
    if not session:
        log_refusal(request, None, [], [], "unauthenticated")
        raise HTTPException(status_code=401, detail="auth_unauthenticated")
    # Enforce CSRF check on mutating requests
    try:
        validate_csrf(request, session)
    except HTTPException:
        log_refusal(request, session.user_id, session.roles, [], "forbidden_csrf")
        raise
    roles = effective_roles(session)
    if roles is None:
        log_refusal(request, session.user_id, session.roles, [], "forbidden_inactive_user")
        raise HTTPException(status_code=403, detail="auth_forbidden_role")
    session.roles = roles
    return session


def require_roles(*allowed_roles: str) -> Callable[[Request, SessionData], SessionData]:
    required = list(allowed_roles)

    def dependency(request: Request, session: SessionData = Depends(require_session)) -> SessionData:
        user_roles = set(session.roles)
        if not user_roles.intersection(required):
            log_refusal(request, session.user_id, session.roles, required, "forbidden_missing_role")
            raise HTTPException(status_code=403, detail="auth_forbidden_role")
        return session

    return dependency


def require_fresh_mfa(max_age_seconds: int = 300) -> Callable[[Request, SessionData], SessionData]:
    def dependency(request: Request, session: SessionData = Depends(require_session)) -> SessionData:
        if not session.is_mfa_fresh(max_age_seconds=max_age_seconds):
            log_refusal(request, session.user_id, session.roles, [], "forbidden_mfa_stale")
            raise HTTPException(status_code=403, detail="auth_mfa_stale")
        return session

    return dependency
