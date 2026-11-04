"""T101: the cost write. Read-modify-write of the purchase cost only, read-after-write verification, bounded visible retries.

Order of events for a released request:
  1. re-check with procurement-service that the buyer released it (a forged message gets no Siweb call at all)
  2. read the supplier record; no record -> pending_link (no write is attempted)
  3. refuse if the ERP value changed since the buyer reviewed it (they must look again)
  4. PUT the cost with the other writable fields resent from the record just read
  5. read it back and compare: cost equals the target and nothing else changed
Every state change is recorded in the attempts table and the hash-chained audit, and announced as
siweb.cost.write_completed.v1 (including each retry, so a failing write is visible and never silent).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from db.tables import outbox, write_attempts
from mmi_common.bus import new_envelope
from mmi_common.outbox import enqueue
from mmi_common.time import get_correlation_id, set_correlation_id
from sqlalchemy import func, insert, select
from sqlalchemy.engine import Connection, Engine

from writer import audit
from writer.allowlist import AllowlistViolation
from writer.client import PermanentError, SiwebWriterClient, TransientError
from writer.procurement import ProcurementApi

log = logging.getLogger("cost-writer")
EVENT_TYPE = "siweb.cost.write_completed.v1"
SUBSCRIPTIONS = {EVENT_TYPE: ["procurement-in"]}
UNCHANGED_FIELDS = ("supplier_reference", "is_preferred", "lead_time_days", "min_order_qty")


def _cents(value: Any) -> int | None:
    """Whole-cent view of a value read from the ERP (which may hold fractional cents) for audit and comparison."""
    return None if value is None else round(float(value))


class ForgedRequestError(Exception):
    """The request id does not refer to a request the buyer released."""


class BlobWriter:
    def put(self, name: str, data: bytes) -> str:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass(frozen=True)
class Outcome:
    request_id: str
    outcome: str            # succeeded / failed / pending_link
    attempts: int
    error: str | None = None


class WriteProcessor:
    def __init__(self, engine: Engine, siweb: SiwebWriterClient, procurement: ProcurementApi, blobs: Any, max_attempts: int = 5,
                 backoff_base: float = 2.0, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.engine, self.siweb, self.procurement, self.blobs = engine, siweb, procurement, blobs
        self.max_attempts, self.backoff_base, self.sleep, self.clock = max_attempts, backoff_base, sleep, clock

    # ---- helpers ----------------------------------------------------------------------------------------
    def _announce(self, conn: Connection, request_id: str, outcome: str, attempts: int, error: str | None) -> None:
        payload = {"cost_write_request_id": request_id, "outcome": outcome, "attempts": attempts, **({"error": error[:200]} if error else {})}
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        uri = self.blobs.put(f"events/{EVENT_TYPE}/{request_id}-{attempts}-{outcome}.json", data)
        enqueue(conn, outbox, new_envelope(EVENT_TYPE, request_id, data, uri, get_correlation_id() or set_correlation_id()))

    def _record(self, request_id: str, actor: str, product: int | None, contact: int | None, attempt: int, outcome: str, action: str, *, status: int | None = None,
                error: str | None = None, previous: int | None = None, new: int | None = None, announce: bool = True) -> None:
        now = self.clock()
        with self.engine.begin() as conn:
            conn.execute(insert(write_attempts).values(request_id=request_id, attempt=attempt, started_at=now, outcome=outcome, http_status=status, error=error and error[:200]))
            audit.record(conn, request_id, actor, action, product, contact, previous, new, {"outcome": outcome, "attempt": attempt, "error": error}, now)
            if announce:
                self._announce(conn, request_id, outcome, attempt, error)

    def _last_attempt(self, request_id: str) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(select(func.max(write_attempts.c.attempt)).where(write_attempts.c.request_id == request_id)).scalar() or 0)

    def _already_succeeded(self, request_id: str) -> bool:
        with self.engine.connect() as conn:
            return bool(conn.execute(select(func.count()).select_from(write_attempts).where(write_attempts.c.request_id == request_id,
                                                                                            write_attempts.c.outcome == "succeeded")).scalar_one())

    # ---- the flow ---------------------------------------------------------------------------------------
    def process(self, request_id: str) -> Outcome:
        released = self.procurement.get_released(request_id)
        if released is None:
            self._record(request_id, "unknown", None, None, 0, "refused", "write.refused_unreleased", error="not released by a buyer", announce=False)
            raise ForgedRequestError(request_id)
        if self._already_succeeded(request_id):
            return Outcome(request_id, "succeeded", 0, "already_done")
        product, contact, target = int(released["product_id"]), released.get("supplier_contact_id"), int(released["cents"])
        actor = str(released.get("reviewed_by") or released.get("requested_by") or "buyer")
        if contact is None:
            return self._finish(request_id, actor, product, None, self._last_attempt(request_id) + 1, "failed", "supplier has no ERP contact id", None, target)
        base, n = self._last_attempt(request_id), 0            # attempts are numbered across re-releases so the history stays readable
        while True:
            n += 1
            attempt = base + n
            try:
                record = self.siweb.get_supplier(product, int(contact))
                if record is None:  # no link in the ERP: never create one, wait for the buyer
                    return self._finish(request_id, actor, product, int(contact), attempt, "pending_link", None, None, target)
                current = record.get("purchase_cost_cents")
                prev_expected = released.get("previous_cents")
                if current is not None and float(current) == target:
                    return self._finish(request_id, actor, product, int(contact), attempt, "succeeded", None, int(current), target)
                if prev_expected is not None and current is not None and _cents(current) != int(prev_expected):
                    return self._finish(request_id, actor, product, int(contact), attempt, "failed", "erp_changed_since_review", _cents(current), target)
                body = {"purchase_cost_cents": target, "supplier_reference": record.get("supplier_reference"), "is_preferred": bool(record.get("is_preferred"))}
                self._record(request_id, actor, product, int(contact), attempt, "sent", "write.sent", previous=_cents(current), new=target, announce=n == 1)
                self.siweb.put_supplier(product, int(contact), body)
                after = self.siweb.get_supplier(product, int(contact))
                problem = self._verify(record, after, target)
                if problem:
                    return self._finish(request_id, actor, product, int(contact), attempt, "failed", problem, _cents(current), target)
                return self._finish(request_id, actor, product, int(contact), attempt, "succeeded", None, _cents(current), target)
            except TransientError as exc:
                if n >= self.max_attempts:
                    return self._finish(request_id, actor, product, int(contact), attempt, "failed", f"gave up after {n} attempts: {exc.detail}", None, target)
                self._record(request_id, actor, product, int(contact), attempt, "retrying", "write.retrying", error=exc.detail, new=target)
                self.sleep(min(self.backoff_base ** (n - 1), 300.0))
            except PermanentError as exc:
                return self._finish(request_id, actor, product, int(contact), attempt, "failed", exc.detail, None, target, status=exc.status)
            except AllowlistViolation as exc:
                log.error("ALLOWLIST_REFUSED %s", exc.reason)
                return self._finish(request_id, actor, product, int(contact), attempt, "failed", f"allowlist: {exc.reason}", None, target)

    @staticmethod
    def _verify(before: dict[str, Any], after: dict[str, Any] | None, target: int) -> str | None:
        if after is None:
            return "verification_failed: record disappeared"
        got = after.get("purchase_cost_cents")
        if got is None or float(got) != float(target):
            return f"verification_failed: cost is {got}, expected {target}"
        for f in UNCHANGED_FIELDS:
            if after.get(f) != before.get(f):
                return f"verification_failed: {f} changed"
        return None

    def _finish(self, request_id: str, actor: str, product: int, contact: int | None, attempt: int, outcome: str, error: str | None, previous: int | None, new: int,
                status: int | None = None) -> Outcome:
        self._record(request_id, actor, product, contact, attempt, outcome, f"write.{outcome}", status=status, error=error, previous=previous, new=new)
        return Outcome(request_id, outcome, attempt, error)
