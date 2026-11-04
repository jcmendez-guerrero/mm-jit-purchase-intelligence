"""Data-quality gates. Nothing is dropped silently: every issue becomes an import_errors row.

Blocking issues keep the record out of downstream decisions (quarantine). Non-blocking issues keep
the record but make the correction visible (for example a movement with no warehouse is stored under
the explicit "unassigned" warehouse, per the spec edge case, and flagged for the buyer).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mapping.normalise import NormalisedMovement, normalise_movement

SALE_REASON = "sale_shipment"


@dataclass(frozen=True)
class Issue:
    entity: str
    external_id: str
    code: str
    detail: str  # never contains personal data or free text
    blocking: bool


@dataclass
class MovementResult:
    movement: NormalisedMovement | None  # None when quarantined
    issues: list[Issue]


def check_movement(raw: dict[str, Any]) -> MovementResult:
    ext = str(raw.get("id"))
    issues: list[Issue] = []
    try:
        mv = normalise_movement(raw)
    except (KeyError, ValueError, TypeError) as exc:
        code = "malformed_expiry" if "expiry" in str(exc) else "malformed_record"
        return MovementResult(None, [Issue("movement", ext, code, type(exc).__name__, True)])
    if mv.timestamp_ambiguous:
        issues.append(Issue("movement", ext, "ambiguous_timestamp", "local time in a DST overlap or gap", True))
    if raw.get("warehouse_id") is None:
        issues.append(Issue("movement", ext, "warehouse_unassigned", "no warehouse; stored as unassigned", False))
    if mv.reason == SALE_REASON and not (mv.reference_type and (mv.reference_id is not None or mv.reference_number)):
        issues.append(Issue("movement", ext, "unreferenced_sale", "sale without a document reference", True))
    blocked = any(i.blocking for i in issues)
    return MovementResult(None if blocked else mv, issues)


def check_lot(raw: dict[str, Any]) -> list[Issue]:
    from mapping.normalise import parse_expiry

    try:
        parse_expiry(raw.get("expiry_date"))
    except ValueError:
        return [Issue("lot", str(raw.get("id") or raw.get("batch_number")), "malformed_expiry", "expiry not a valid date", True)]
    return []
