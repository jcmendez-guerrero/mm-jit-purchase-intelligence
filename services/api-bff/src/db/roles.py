"""Durable user roles for the BFF (US1, FR-001).

A role change, its hash-chained audit event and its mirror-outbox row are written in ONE transaction, so a change can
never exist without its audit trail or without being queued for procurement (which decides approval eligibility).
Refusals of authenticated requests are audited as well; anonymous refusals are not stored (a flood must not grow the table).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from audit import ChainCheck, verify_chain
from audit import append as append_audit
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Connection, Engine

from .tables import audit_events, role_mirror_outbox, user_roles

ROLES = ("viewer", "buyer", "approver", "admin")
BACKOFF_BASE_SECONDS = 30
BACKOFF_CAP_SECONDS = 3600


class RoleError(Exception):
    """Carries a stable error code (see packages/contracts/errors/error_codes.json)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RoleRecord:
    user_id: str
    roles: tuple[str, ...]
    active: bool
    revision: int
    updated_by: str
    updated_at: datetime


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _record(r: Any) -> RoleRecord:
    return RoleRecord(r.user_id, tuple(r.roles), bool(r.active), int(r.revision), r.updated_by, _aware(r.updated_at))


def _holders(conn: Connection, role: str, exclude: str | None = None) -> int:
    rows = conn.execute(select(user_roles.c.user_id, user_roles.c.roles).where(user_roles.c.active)).all()
    return sum(1 for r in rows if role in r.roles and r.user_id != exclude)


class RoleStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    # ---- reads ----
    def get(self, user_id: str) -> RoleRecord | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(user_roles).where(user_roles.c.user_id == user_id)).first()
        return _record(row) if row else None

    def list(self) -> list[RoleRecord]:
        with self.engine.connect() as conn:
            return [_record(r) for r in conn.execute(select(user_roles).order_by(user_roles.c.user_id)).all()]

    def approver_count(self) -> int:
        with self.engine.connect() as conn:
            return _holders(conn, "approver")

    # ---- writes ----
    def set_roles(self, user_id: str, roles: list[str], actor: str, active: bool = True, now: datetime | None = None) -> RoleRecord:
        if any(r not in ROLES for r in roles):
            raise RoleError("roles_invalid")
        new_roles = sorted(set(roles))
        now = now or datetime.now(UTC)
        with self.engine.begin() as conn:
            before = conn.execute(select(user_roles).where(user_roles.c.user_id == user_id)).first()
            for role, code in (("approver", "approval_fewer_than_two_approvers"), ("admin", "roles_last_admin")):
                current, others = _holders(conn, role), _holders(conn, role, exclude=user_id)
                projected = others + (1 if (role in new_roles and active) else 0)
                floor = 2 if role == "approver" else 1
                if projected < floor and projected < current:     # only a change that REDUCES the holders below the floor is refused
                    raise RoleError(code)
            revision = (before.revision + 1) if before else 1
            values = {"roles": new_roles, "active": active, "revision": revision, "updated_by": actor, "updated_at": now}
            if before is None:
                conn.execute(insert(user_roles).values(user_id=user_id, **values))
            else:
                conn.execute(update(user_roles).where(user_roles.c.user_id == user_id).values(**values))
            append_audit(conn, actor, "roles.changed", "user_roles", user_id,
                         before=None if before is None else {"roles": list(before.roles), "active": bool(before.active), "revision": before.revision},
                         after={"roles": new_roles, "active": active, "revision": revision}, now=now)
            conn.execute(insert(role_mirror_outbox).values(user_id=user_id, roles_snapshot=new_roles, active=active, revision=revision, status="pending", attempts=0,
                                                           next_attempt_at=now, created_at=now))
            return RoleRecord(user_id, tuple(new_roles), active, revision, actor, now)

    def replace_all(self, users: dict[str, list[str]], actor: str = "system") -> None:
        """Seeding and tests: replaces the registry without audit or mirror rows. Refused anywhere but SQLite."""
        self._sqlite_only()
        now = datetime.now(UTC)
        with self.engine.begin() as conn:
            conn.execute(delete(user_roles))
            for uid, roles in users.items():
                conn.execute(insert(user_roles).values(user_id=uid, roles=sorted(set(roles)), active=True, revision=1, updated_by=actor, updated_at=now))

    def seed_if_empty(self, users: dict[str, list[str]], actor: str = "system") -> bool:
        """Development seed: used only when the registry has no users at all."""
        if self.list():
            return False
        now = datetime.now(UTC)
        for uid, roles in users.items():
            self.set_roles(uid, roles, actor=actor, now=now)
        return True

    def reset_for_tests(self) -> None:
        self._sqlite_only()
        with self.engine.begin() as conn:
            conn.execute(delete(role_mirror_outbox))
            conn.execute(delete(audit_events))

    def _sqlite_only(self) -> None:
        if self.engine.dialect.name != "sqlite":
            raise RuntimeError("only available on the local SQLite stand-in, never on the real database")

    # ---- audit ----
    def record_refusal(self, actor: str, action: str, subject: str, before: Any = None, after: Any = None, now: datetime | None = None) -> None:
        with self.engine.begin() as conn:
            append_audit(conn, actor, action, "access" if action == "access.refused" else "user_roles", subject[:60], before=before, after=after, now=now)

    def audit_view(self, limit: int | None = None) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(audit_events).order_by(audit_events.c.id)).all()
        out = []
        for r in rows:
            after, before = r.after or {}, r.before or {}
            ok = r.action == "roles.changed"
            out.append({
                "timestamp": _aware(r.ts).isoformat(), "actor": r.actor, "action": r.action, "target_user": r.entity_id,
                "old_roles": before.get("roles", []), "new_roles": after.get("roles", []), "success": ok,
                "refusal_reason": None if ok else after.get("reason"),
            })
        return out[-limit:] if limit else out

    def verify_audit(self) -> ChainCheck:
        with self.engine.connect() as conn:
            return verify_chain(conn)

    # ---- mirror outbox ----
    def due_mirrors(self, now: datetime, limit: int = 100) -> list[Any]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(role_mirror_outbox).where(role_mirror_outbox.c.status == "pending").order_by(role_mirror_outbox.c.id).limit(limit * 5)).all()
        return [r for r in rows if r.next_attempt_at is None or _aware(r.next_attempt_at) <= now][:limit]

    def mark_sent(self, outbox_id: int, now: datetime) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(role_mirror_outbox).where(role_mirror_outbox.c.id == outbox_id).values(status="sent", sent_at=now, last_error_key=None))

    def mark_attempt_failed(self, outbox_id: int, now: datetime, error_key: str, max_attempts: int) -> None:
        with self.engine.begin() as conn:
            attempts = (conn.execute(select(role_mirror_outbox.c.attempts).where(role_mirror_outbox.c.id == outbox_id)).scalar() or 0) + 1
            delay = min(BACKOFF_BASE_SECONDS * (2 ** (attempts - 1)), BACKOFF_CAP_SECONDS)
            conn.execute(update(role_mirror_outbox).where(role_mirror_outbox.c.id == outbox_id).values(
                attempts=attempts, last_error_key=error_key, status="failed" if attempts >= max_attempts else "pending",
                next_attempt_at=now + timedelta(seconds=delay)))

    def requeue_failed(self, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        with self.engine.begin() as conn:
            res = conn.execute(update(role_mirror_outbox).where(role_mirror_outbox.c.status == "failed").values(status="pending", attempts=0, next_attempt_at=now))
            return int(res.rowcount)

    def mirror_status(self, now: datetime | None = None, item_limit: int = 20) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        with self.engine.connect() as conn:
            counts = dict(conn.execute(select(role_mirror_outbox.c.status, func.count()).group_by(role_mirror_outbox.c.status)).all())
            open_rows = conn.execute(select(role_mirror_outbox).where(role_mirror_outbox.c.status.in_(("pending", "failed"))).order_by(role_mirror_outbox.c.id)).all()
        oldest = min((_aware(r.created_at) for r in open_rows if r.status == "pending"), default=None)
        return {
            "pending": counts.get("pending", 0), "failed": counts.get("failed", 0), "sent": counts.get("sent", 0),
            "oldest_pending_seconds": int((now - oldest).total_seconds()) if oldest else 0,
            "items": [{"id": r.id, "user_id": r.user_id, "status": r.status, "attempts": r.attempts, "last_error_key": r.last_error_key} for r in open_rows[:item_limit]],
        }
