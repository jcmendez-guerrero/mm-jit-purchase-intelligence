"""Admin role assignment and revocation with audit logging and separation-of-duties check (T137).

Guarantees at least two eligible approvers exist in the system to prevent single-person deadlock
or self-approval. Records all changes and refused attempts in an audit log.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from auth.session import SessionData
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from routes.rbac import require_roles

logger = logging.getLogger("mmi.api_bff.admin_roles")

router = APIRouter(prefix="/admin/roles", tags=["config"])


@dataclass
class AuditRecord:
    timestamp: str
    actor: str
    action: str
    target_user: str
    old_roles: list[str]
    new_roles: list[str]
    success: bool
    refusal_reason: str | None = None


# Persistent in-memory user registry for the BFF
_users: dict[str, list[str]] = {
    "buyer-1": ["viewer", "buyer"],
    "buyer-2": ["viewer", "buyer"],
    "approver-1": ["viewer", "approver"],
    "approver-2": ["viewer", "approver"],
    "admin-1": ["viewer", "admin"],
}

_audit_log: list[AuditRecord] = []


def get_user_roles(user_id: str) -> list[str] | None:
    return _users.get(user_id)


def set_initial_users(users: dict[str, list[str]]) -> None:
    global _users
    _users = {k: list(v) for k, v in users.items()}


def get_audit_log() -> list[dict[str, Any]]:
    return [asdict(r) for r in _audit_log]


def clear_audit_log() -> None:
    _audit_log.clear()


def count_eligible_approvers() -> int:
    return sum(1 for roles in _users.values() if "approver" in roles)


def has_at_least_two_eligible_approvers() -> bool:
    return count_eligible_approvers() >= 2


class RoleUpdateRequest(BaseModel):
    roles: list[str] = Field(..., description="List of roles: viewer, buyer, approver, admin")


@router.get("")
def list_roles(session: SessionData = Depends(require_roles("admin"))) -> dict[str, Any]:
    return {
        "users": [{"user_id": uid, "roles": roles} for uid, roles in _users.items()],
        "eligible_approvers_count": count_eligible_approvers(),
    }


@router.put("/{user_id}")
def update_user_roles(
    user_id: str,
    body: RoleUpdateRequest,
    session: SessionData = Depends(require_roles("admin")),
) -> dict[str, Any]:
    valid_roles = {"viewer", "buyer", "approver", "admin"}
    invalid = set(body.roles) - valid_roles
    if invalid:
        raise HTTPException(status_code=422, detail=f"invalid roles: {list(invalid)}")

    old_roles = _users.get(user_id, ["viewer"])
    new_roles = sorted(set(body.roles))

    # Check if this change would reduce the count of eligible approvers below 2
    was_approver = "approver" in old_roles
    will_be_approver = "approver" in new_roles

    current_approvers = count_eligible_approvers()
    projected_approvers = current_approvers - (1 if was_approver and not will_be_approver else 0)

    if projected_approvers < 2:
        reason = "at least two eligible approvers required to maintain separation of duties"
        _audit_log.append(
            AuditRecord(
                timestamp=datetime.now(UTC).isoformat(),
                actor=session.user_id,
                action="update_roles_refused",
                target_user=user_id,
                old_roles=old_roles,
                new_roles=new_roles,
                success=False,
                refusal_reason=reason,
            )
        )
        raise HTTPException(status_code=409, detail=reason)

    _users[user_id] = new_roles
    _audit_log.append(
        AuditRecord(
            timestamp=datetime.now(UTC).isoformat(),
            actor=session.user_id,
            action="update_roles",
            target_user=user_id,
            old_roles=old_roles,
            new_roles=new_roles,
            success=True,
            refusal_reason=None,
        )
    )
    return {"user_id": user_id, "roles": new_roles}
