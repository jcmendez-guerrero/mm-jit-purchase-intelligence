"""T077: staleness and abnormal-jump rules (defaults: 30 days, +/-25 %), configurable through cost_rule_config."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from db.tables import cost_rule_config
from sqlalchemy import select
from sqlalchemy.engine import Connection

DEFAULT_STALE_DAYS = 30
DEFAULT_JUMP = Decimal("0.25")


@dataclass(frozen=True)
class CostRules:
    stale_days: int = DEFAULT_STALE_DAYS
    jump_threshold: Decimal = DEFAULT_JUMP


def load_rules(conn: Connection) -> CostRules:
    cfg = {r.key: Decimal(str(r.value)) for r in conn.execute(select(cost_rule_config)).all()}
    return CostRules(int(cfg.get("stale_days", DEFAULT_STALE_DAYS)), cfg.get("jump_threshold", DEFAULT_JUMP))


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def is_stale(verified_at: datetime, now: datetime, rules: CostRules) -> bool:
    return _aware(now) - _aware(verified_at) > timedelta(days=rules.stale_days)


def is_abnormal_jump(previous: Decimal | None, new: Decimal, rules: CostRules) -> bool:
    """True when the relative change exceeds the threshold. No previous value (or a zero one) is not a jump."""
    if previous is None or previous <= 0:
        return False
    return abs(new - previous) / previous > rules.jump_threshold


def status(jump_flag: bool, jump_confirmed: bool, verified_at: datetime, now: datetime, rules: CostRules) -> str:
    """blocked_jump outranks stale: an unconfirmed jump must be resolved before anything else."""
    if jump_flag and not jump_confirmed:
        return "blocked_jump"
    return "stale" if is_stale(verified_at, now, rules) else "ok"
