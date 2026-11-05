"""T151: the production user directory. The BFF mirrors every audited role change here; approval eligibility reads it.

``active_approvers`` is what submit-for-approval needs for the "at least two users could satisfy separation of duties"
rule (FR-029). The registry itself is administered in the BFF; this table is the durable copy procurement decides from.
"""

from __future__ import annotations

from datetime import UTC, datetime

from audit.chain import append as audit
from db.tables import user_roles
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine

ROLES = ("viewer", "buyer", "approver", "admin")


class DirectoryError(Exception):
    code = "unknown_role"


def _approvers(conn: Connection) -> set[str]:
    return {r.user_id for r in conn.execute(select(user_roles).where(user_roles.c.active)).all() if "approver" in r.roles}


class ConnUserDirectory:
    """Reads inside a caller's transaction (what a request handler uses, so it sees one consistent snapshot)."""

    def __init__(self, conn: Connection) -> None:
        self.conn = conn

    def active_approvers(self) -> set[str]:
        return _approvers(self.conn)


class DbUserDirectory:
    """Implements approvals.workflow.UserDirectory with its own connection."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def bind(self, conn: Connection) -> ConnUserDirectory:
        return ConnUserDirectory(conn)

    def active_approvers(self) -> set[str]:
        with self.engine.connect() as conn:
            return _approvers(conn)


def set_roles(conn: Connection, user_id: str, roles: list[str], actor: str, active: bool = True, now: datetime | None = None) -> None:
    bad = [r for r in roles if r not in ROLES]
    if bad:
        raise DirectoryError(f"unknown roles: {bad}")
    now = now or datetime.now(UTC)
    before = conn.execute(select(user_roles).where(user_roles.c.user_id == user_id)).first()
    values = {"roles": sorted(set(roles)), "active": active, "updated_by": actor, "updated_at": now}
    if before is None:
        conn.execute(insert(user_roles).values(user_id=user_id, **values))
    else:
        conn.execute(update(user_roles).where(user_roles.c.user_id == user_id).values(**values))
    audit(conn, actor, "user.roles_set", "user", user_id, before=None if before is None else {"roles": before.roles, "active": before.active},
          after={"roles": values["roles"], "active": active}, now=now)
