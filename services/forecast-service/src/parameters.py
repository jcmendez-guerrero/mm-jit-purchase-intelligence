"""T092: editable forecast parameters. Only keys on the approved list, within their ranges, effective-dated and revisioned.

A run reads the parameters in force on its date and records the revision of each one it used, so the same inputs and the same
parameters give the same forecast, and a changed parameter gives a new, separately identified run.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from audit import append as audit
from backtest.runner import BacktestConfig
from db.tables import forecast_parameters
from sqlalchemy import func, insert, select
from sqlalchemy.engine import Connection

SCOPE = "global"


@dataclass(frozen=True)
class Spec:
    kind: str                    # int / decimal
    low: Decimal
    high: Decimal
    default: Decimal


APPROVED: dict[str, Spec] = {
    "lead_time": Spec("int", Decimal(1), Decimal(60), Decimal(7)),
    "backtest.min_history": Spec("int", Decimal(14), Decimal(730), Decimal(56)),
    "backtest.min_windows": Spec("int", Decimal(1), Decimal(100), Decimal(30)),
    "backtest.min_gain": Spec("decimal", Decimal(0), Decimal("0.5"), Decimal("0.05")),
    "backtest.max_censored_share": Spec("decimal", Decimal(0), Decimal(1), Decimal("0.5")),
}


class ParameterError(Exception):
    def __init__(self, message: str, code: str = "policy_out_of_range") -> None:
        super().__init__(message)
        self.code = code


class ParameterConflict(Exception):
    code = "revision_conflict"

    def __init__(self, current: int) -> None:
        super().__init__(f"current revision is {current}")
        self.current_revision = current


def _coerce(key: str, value: Any) -> Decimal:
    spec = APPROVED.get(key)
    if spec is None:
        raise ParameterError("parameter not on the approved list", "unknown_parameter")
    if isinstance(value, float | bool):
        raise ParameterError("use an exact number")
    try:
        d = Decimal(str(value))
    except Exception as exc:
        raise ParameterError("not a number") from exc
    if not d.is_finite() or not (spec.low <= d <= spec.high) or (spec.kind == "int" and d != d.to_integral_value()):
        raise ParameterError("out of range")
    return d


def _current_revision(conn: Connection, key: str) -> int:
    return int(conn.execute(select(func.max(forecast_parameters.c.revision)).where(forecast_parameters.c.scope == SCOPE, forecast_parameters.c.key == key)).scalar() or 0)


def save_parameter(conn: Connection, key: str, value: Any, actor: str, *, valid_from: date | None = None, expected_revision: int | None = None,
                   today: date | None = None, now: datetime | None = None) -> int:
    d = _coerce(key, value)
    today = today or datetime.now(UTC).date()
    start = valid_from or today
    if start < today:
        raise ParameterError("a parameter cannot start in the past: earlier runs keep what they used")
    cur = _current_revision(conn, key)
    if expected_revision is not None and expected_revision != cur:
        raise ParameterConflict(cur)
    rev = cur + 1
    pid = str(uuid.uuid4())
    last = conn.execute(select(forecast_parameters).where(forecast_parameters.c.scope == SCOPE, forecast_parameters.c.key == key)
                        .order_by(forecast_parameters.c.revision.desc()).limit(1)).first()
    before = None if last is None else {"value": str(last.value), "revision": int(last.revision), "valid_from": last.valid_from.isoformat()}
    conn.execute(insert(forecast_parameters).values(id=pid, scope=SCOPE, key=key, value=str(d), valid_from=start, revision=rev, changed_by=actor))
    audit(conn, actor, "parameter.saved", "parameter", key, before=before, after={"value": str(d), "revision": rev, "valid_from": start.isoformat()}, now=now)
    return rev


def effective(conn: Connection, as_of: date) -> tuple[dict[str, Decimal], dict[str, int]]:
    """Values in force on ``as_of`` (defaults where nothing was set) and the revision of every one that was set."""
    values = {k: s.default for k, s in APPROVED.items()}
    revisions: dict[str, int] = {}
    for key in APPROVED:
        row = conn.execute(select(forecast_parameters).where(forecast_parameters.c.scope == SCOPE, forecast_parameters.c.key == key, forecast_parameters.c.valid_from <= as_of)
                           .order_by(forecast_parameters.c.valid_from.desc(), forecast_parameters.c.revision.desc()).limit(1)).first()
        if row is not None:
            values[key] = Decimal(str(row.value))
            revisions[key] = int(row.revision)
    return values, revisions


def listing(conn: Connection, as_of: date) -> list[dict[str, Any]]:
    values, revisions = effective(conn, as_of)
    return [{"key": k, "value": str(values[k]), "default": str(s.default), "min": str(s.low), "max": str(s.high), "kind": s.kind,
             "revision": _current_revision(conn, k), "in_force_revision": revisions.get(k)} for k, s in APPROVED.items()]


def config_from_parameters(conn: Connection, as_of: date) -> tuple[Any, dict[str, int]]:
    from runs.runner import RunConfig

    v, revisions = effective(conn, as_of)
    b = BacktestConfig()
    b = replace(b, min_history=int(v["backtest.min_history"]), min_windows=int(v["backtest.min_windows"]), min_gain=v["backtest.min_gain"],
                max_censored_share=float(v["backtest.max_censored_share"]), lead_time=int(v["lead_time"]))
    return RunConfig(lead_time=int(v["lead_time"]), backtest=b), revisions
