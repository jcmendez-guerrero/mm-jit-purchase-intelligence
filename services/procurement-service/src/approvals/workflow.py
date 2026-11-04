"""T097: submit / approve state machine with separation of duties and MFA freshness.

draft --submit--> submitted --approve--> approved --(export)--> exported
An edit after submission returns the proposal to draft (see proposals/edit.py). The approver must hold the approver role,
must be neither the creator nor the last editor, and must have authenticated with a second factor within the last
5 minutes. Approval is recorded against the proposal version it saw, so a later edit can never ride on an old approval.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from audit.chain import append as audit
from db.tables import approvals, proposals
from mmi_common.auth import Principal
from proposals.edit import ConcurrencyError, ProposalStateError
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

MFA_MAX_AGE = timedelta(minutes=5)


class ApprovalError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class UserDirectory(Protocol):
    def active_approvers(self) -> set[str]:
        """Subjects of active users holding the approver role."""


def _get(conn: Connection, proposal_id: str):  # type: ignore[no-untyped-def]
    p = conn.execute(select(proposals).where(proposals.c.id == proposal_id)).first()
    if p is None:
        raise ProposalStateError("unknown proposal")
    return p


def submit(conn: Connection, proposal_id: str, actor: str, expected_version: int, users: UserDirectory, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    p = _get(conn, proposal_id)
    if p.status != "draft":
        raise ProposalStateError(f"only a draft can be submitted, this one is {p.status}")
    if p.version != expected_version:
        raise ConcurrencyError(f"proposal is at version {p.version}, not {expected_version}")
    eligible = users.active_approvers() - {p.created_by, p.last_edited_by}
    if not eligible:  # FR-029: refuse to enter approval when nobody could satisfy the separation-of-duties rule
        raise ApprovalError("no_eligible_approver")
    conn.execute(update(proposals).where(proposals.c.id == proposal_id).values(status="submitted", submitted_at=now, updated_at=now))
    audit(conn, actor, "proposal.submitted", "proposal", proposal_id, before={"status": "draft"}, after={"status": "submitted", "version": p.version}, now=now)


def decide(conn: Connection, proposal_id: str, principal: Principal, expected_version: int, approve: bool = True, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    p = _get(conn, proposal_id)
    if "approver" not in principal.roles:
        raise ApprovalError("not_an_approver")
    if p.status != "submitted":
        raise ProposalStateError(f"only a submitted proposal can be decided, this one is {p.status}")
    if p.version != expected_version:
        raise ConcurrencyError(f"proposal is at version {p.version}, not {expected_version}")
    if principal.subject in (p.created_by, p.last_edited_by):
        raise ApprovalError("separation_of_duties")
    if not principal.mfa_fresh(MFA_MAX_AGE, now) or principal.auth_time is None:
        raise ApprovalError("mfa_required")
    decision = "approved" if approve else "rejected"
    conn.execute(insert(approvals).values(proposal_id=proposal_id, approver_id=principal.subject, decided_at=now, decision=decision,
                                          mfa_auth_time=principal.auth_time, proposal_version=p.version))
    status = "approved" if approve else "draft"
    conn.execute(update(proposals).where(proposals.c.id == proposal_id).values(status=status, updated_at=now))
    audit(conn, principal.subject, f"proposal.{decision}", "proposal", proposal_id, before={"status": "submitted"},
          after={"status": status, "version": p.version, "mfa_auth_time": principal.auth_time.isoformat()}, now=now)


def is_approval_valid(conn: Connection, proposal_id: str) -> bool:
    """True when the latest approval refers to the current version of an approved proposal."""
    p = _get(conn, proposal_id)
    last = conn.execute(select(approvals).where(approvals.c.proposal_id == proposal_id).order_by(approvals.c.id.desc()).limit(1)).first()
    return bool(p.status in ("approved", "exported") and last and last.decision == "approved" and last.proposal_version == p.version)

