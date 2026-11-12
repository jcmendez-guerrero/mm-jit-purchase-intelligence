"""Validation of the read-only operations snapshots (backup, cost, queues) supplied by the platform (feature 010, D3).

Money is a decimal string (never a float), the timestamp must be timezone-aware and not in the future, and unknown fields
are refused. The original timestamp string is kept next to the parsed value by the store.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr, StringConstraints, ValidationError, model_validator

Money = Annotated[StrictStr, StringConstraints(pattern=r"^[0-9]+(\.[0-9]{1,2})?$")]
Code = Annotated[StrictStr, StringConstraints(pattern=r"^[a-z0-9._-]{1,64}$")]
FUTURE_TOLERANCE = timedelta(minutes=5)


class SnapshotError(Exception):
    code = "snapshot_invalid"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Backup(_Strict):
    last_success_at: datetime | None = None
    last_restore_drill_at: datetime | None = None


class Limits(_Strict):
    min_replicas: int | None = None
    max_replicas: int | None = None
    job_parallelism: int | None = None


class Cost(_Strict):
    currency: Literal["EUR"]
    budget: Money
    month_to_date: Money
    projected: Money
    partial_month: StrictBool
    limits: Limits | None = None


class DeadLetter(_Strict):
    queue: Code
    count: int
    reason_code: Annotated[StrictStr, StringConstraints(pattern=r"^[a-z0-9_]{1,64}$")] | None = None


class Queues(_Strict):
    dead_lettered: list[DeadLetter] = []


class Snapshot(_Strict):
    kind: Literal["backup", "cost", "queues"]
    captured_at: datetime
    status: Literal["ok", "unavailable"]
    backup: Backup | None = None
    cost: Cost | None = None
    queues: Queues | None = None

    @model_validator(mode="after")
    def _payload_matches_kind(self) -> Snapshot:
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must carry a time zone")
        if self.status == "ok" and getattr(self, self.kind) is None:
            raise ValueError("payload missing for kind")
        return self

    def payload(self) -> dict:
        body = getattr(self, self.kind)
        return {} if body is None else body.model_dump(mode="json")


def parse_snapshot(raw: object, now: datetime | None = None) -> Snapshot:
    now = now or datetime.now(UTC)
    try:
        snap = Snapshot.model_validate(raw)
    except (ValidationError, TypeError, ValueError) as exc:
        raise SnapshotError(type(exc).__name__) from exc
    if snap.captured_at.astimezone(UTC) > now + FUTURE_TOLERANCE:
        raise SnapshotError("captured_in_the_future")
    return snap
