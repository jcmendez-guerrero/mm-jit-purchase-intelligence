"""Admin role management (FR-001, T137): durable roles, two-approver rule, last-admin guard, audit, and the procurement mirror.

Every change is stored in the ``bff`` schema together with its hash-chained audit event and a mirror-outbox row; the same
request then tries one mirror pass, and ``python -m worker`` retries what failed. Errors are stable codes, never sentences.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from auth.session import SessionData
from db.engine import make_engine
from db.roles import ROLES, RoleError, RoleStore
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from routes.rbac import require_fresh_mfa, require_roles

logger = logging.getLogger("mmi.api_bff.admin_roles")

router = APIRouter(prefix="/admin/roles", tags=["config"])

DEV_USERS: dict[str, list[str]] = {
    "viewer-1": ["viewer"],
    "buyer-1": ["viewer", "buyer"],
    "buyer-2": ["viewer", "buyer"],
    "approver-1": ["viewer", "approver"],
    "approver-2": ["viewer", "approver"],
    "admin-1": ["viewer", "admin"],
}

_store: RoleStore | None = None


def get_store() -> RoleStore:
    global _store
    if _store is None:
        _store = RoleStore(make_engine())
        if os.environ.get("MMI_ENV", "dev") != "prod" and os.environ.get("MMI_ENABLE_DEV_LOGIN") == "1":
            _store.seed_if_empty(DEV_USERS)          # local development only; production roles are administered, never seeded
    return _store


def set_store(store: RoleStore | None) -> None:
    global _store
    _store = store


# ---- compatibility helpers used by tests and other routes ----
def get_user_roles(user_id: str) -> list[str] | None:
    rec = get_store().get(user_id)
    return list(rec.roles) if rec else None


def set_initial_users(users: dict[str, list[str]]) -> None:
    get_store().replace_all(users)


def get_audit_log() -> list[dict[str, Any]]:
    return get_store().audit_view()


def clear_audit_log() -> None:
    get_store().reset_for_tests()


def count_eligible_approvers() -> int:
    return get_store().approver_count()


def has_at_least_two_eligible_approvers() -> bool:
    return count_eligible_approvers() >= 2


class RoleUpdateRequest(BaseModel):
    roles: list[str] = Field(..., description="List of roles: viewer, buyer, approver, admin")
    active: bool = True
    expected_revision: int | None = Field(None, ge=0, description="When set and different from the stored revision the call fails with 409 roles_conflict.")


@router.get("")
def list_roles(session: SessionData = Depends(require_roles("admin"))) -> dict[str, Any]:
    store = get_store()
    return {
        "users": [{"user_id": r.user_id, "roles": list(r.roles), "active": r.active, "revision": r.revision} for r in store.list()],
        "eligible_approvers_count": store.approver_count(),
        "valid_roles": list(ROLES),
    }


@router.get("/mirror")
def mirror_status(session: SessionData = Depends(require_roles("admin"))) -> dict[str, Any]:
    return get_store().mirror_status()


@router.post("/mirror/retry")
def mirror_retry(background: BackgroundTasks, session: SessionData = Depends(require_roles("admin")),
                 _fresh: SessionData = Depends(require_fresh_mfa())) -> dict[str, Any]:
    n = get_store().requeue_failed()
    background.add_task(_mirror_pass)
    return {"requeued": n}


@router.put("/{user_id}")
def update_user_roles(user_id: str, body: RoleUpdateRequest, background: BackgroundTasks,
                      session: SessionData = Depends(require_roles("admin")), _fresh: SessionData = Depends(require_fresh_mfa())) -> dict[str, Any]:
    store = get_store()
    old = store.get(user_id)
    try:
        rec = store.set_roles(user_id, body.roles, actor=session.user_id, active=body.active, expected_revision=body.expected_revision)
    except RoleError as exc:
        store.record_refusal(session.user_id, "roles.refused", user_id, before={"roles": list(old.roles) if old else []},
                             after={"roles": sorted(set(body.roles)), "reason": exc.code})
        status = 422 if exc.code == "roles_invalid" else 409
        raise HTTPException(status_code=status, detail=exc.code) from exc
    background.add_task(_mirror_pass)                  # best effort now; the worker retries anything that fails
    return {"user_id": rec.user_id, "roles": list(rec.roles), "active": rec.active, "revision": rec.revision}


def _mirror_pass() -> None:
    """One immediate relay pass. Never raises: a failure stays queued and visible in /admin/roles/mirror."""
    try:
        from clients.procurement import RoleMirrorClient
        from worker import drain_once

        drain_once(get_store(), RoleMirrorClient())
    except Exception as exc:
        logger.warning("ROLE_MIRROR_PASS_FAILED reason=%s", type(exc).__name__)
