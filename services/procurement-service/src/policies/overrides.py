"""T089: recommended versus effective safety stock (and min/max). The system recommends; a person may ask for a different value, which
only applies once an approver other than the requester approves it. A rejected request keeps the recommendation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from audit.chain import append as audit
from db.tables import policy_override_requests, proposal_lines, proposals
from mmi_common.auth import Principal
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Row

from policies.service import PolicyError

FIELDS = ("safety_stock", "min", "max")
REASON_MIN = 5


class OverrideRequestError(PolicyError):
    pass


def recommended_safety_stock(conn: Connection, variant_id: int) -> int | None:
    """What the engine recommended for the variant in the newest proposal; None when it has never been proposed."""
    r = conn.execute(select(proposal_lines.c.safety_stock).join(proposals, proposals.c.id == proposal_lines.c.proposal_id)
                     .where(proposal_lines.c.variant_id == variant_id).order_by(proposals.c.created_at.desc()).limit(1)).first()
    return None if r is None or r.safety_stock is None else int(r.safety_stock)


def request_override(conn: Connection, variant_id: int, field: str, requested: int, reason: str, actor: str, recommended: int | None, now: datetime | None = None) -> Row[Any]:
    if field not in FIELDS or variant_id < 1 or not (0 <= requested <= 1_000_000):
        raise OverrideRequestError("override out of range")
    reason = (reason or "").strip()
    if len(reason) < REASON_MIN or len(reason) > 500:
        raise OverrideRequestError("reason required", "override_reason_required")
    if conn.execute(select(policy_override_requests.c.id).where(
            policy_override_requests.c.variant_id == variant_id, policy_override_requests.c.field == field, policy_override_requests.c.status == "pending")).first():
        raise OverrideRequestError("a request is already pending", "policy_override_pending")
    now = now or datetime.now(UTC)
    rid = str(uuid.uuid4())
    conn.execute(insert(policy_override_requests).values(id=rid, variant_id=variant_id, field=field, recommended_value=recommended or 0, requested_value=requested, reason=reason,
                                                         status="pending", requested_by=actor, requested_at=now, recommendation_changed=False))
    audit(conn, actor, "policy_override.requested", "policy_override", rid, after={"variant_id": variant_id, "field": field, "recommended": recommended, "requested": requested, "reason": reason}, now=now)
    return _get(conn, rid)


def _get(conn: Connection, rid: str) -> Row[Any]:
    r = conn.execute(select(policy_override_requests).where(policy_override_requests.c.id == rid)).first()
    if r is None:
        raise OverrideRequestError("unknown request", "policy_override_not_found")
    return r


def decide(conn: Connection, rid: str, principal: Principal, approve: bool, current_recommended: int | None, now: datetime | None = None) -> Row[Any]:
    """Approver other than the requester; no extra second factor (decided 2026-11-05). Flags when the recommendation moved since the request."""
    if "approver" not in principal.roles:
        raise OverrideRequestError("approver role required", "not_an_approver")
    r = _get(conn, rid)
    if r.status != "pending":
        raise OverrideRequestError("not pending", "policy_override_not_pending")
    if r.requested_by == principal.subject:
        raise OverrideRequestError("self approval", "policy_override_self_approval")
    now = now or datetime.now(UTC)
    changed = current_recommended is not None and current_recommended != r.recommended_value
    conn.execute(update(policy_override_requests).where(policy_override_requests.c.id == rid).values(
        status="approved" if approve else "rejected", decided_by=principal.subject, decided_at=now, recommendation_changed=changed))
    audit(conn, principal.subject, "policy_override.approved" if approve else "policy_override.rejected", "policy_override", rid,
          before={"status": "pending", "recommended": r.recommended_value}, after={"requested": r.requested_value, "recommendation_changed": changed, "current_recommended": current_recommended}, now=now)
    return _get(conn, rid)


def revert(conn: Connection, rid: str, principal: Principal, now: datetime | None = None) -> Row[Any]:
    r = _get(conn, rid)
    if r.status != "approved":
        raise OverrideRequestError("not approved", "policy_override_not_pending")
    if "approver" not in principal.roles and principal.subject != r.requested_by:
        raise OverrideRequestError("approver role required", "not_an_approver")
    now = now or datetime.now(UTC)
    conn.execute(update(policy_override_requests).where(policy_override_requests.c.id == rid).values(status="reverted"))
    audit(conn, principal.subject, "policy_override.reverted", "policy_override", rid, before={"status": "approved"}, after={"status": "reverted"}, now=now)
    return _get(conn, rid)


def effective_overrides(conn: Connection) -> dict[tuple[int, str], int]:
    """Latest approved request per (variant, field)."""
    out: dict[tuple[int, str], int] = {}
    for r in conn.execute(select(policy_override_requests).where(policy_override_requests.c.status == "approved").order_by(policy_override_requests.c.decided_at)).all():
        out[(r.variant_id, r.field)] = int(r.requested_value)
    return out


def queue(conn: Connection, status: str | None = "pending") -> list[Row[Any]]:
    q = select(policy_override_requests).order_by(policy_override_requests.c.requested_at.desc())
    if status:
        q = q.where(policy_override_requests.c.status == status)
    return list(conn.execute(q).all())
