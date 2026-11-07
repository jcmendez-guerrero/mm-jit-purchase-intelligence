"""T100 + T140: cost write requests (the only ERP write), their review, release and outcome.

Cases: (a) the ERP has a product-supplier record with no cost and the buyer enters one; (b) the buyer confirms an order at
a cost that differs from the ERP. If the ERP holds no record linking the pair, nothing is requested from the ERP: the
request is parked as ``pending_link`` and the cost stays local until the buyer creates the link and re-releases it
(FR-040). Release needs the buyer role and a second factor authenticated within 5 minutes. The writer re-checks the request
through this service before touching the ERP, so a forged message cannot trigger a write.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from audit.chain import append as audit
from db.tables import cost_write_requests, erp_supplier_links, product_refs, supplier_costs
from mmi_common.auth import Principal
from mmi_common.time import get_correlation_id, set_correlation_id
from proposals.publisher import WRITE_REQUESTED, BlobWriter, publish
from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection, Row

from costs.margin import BELOW_MINIMUM, UNAVAILABLE, Evaluation, evaluate
from costs.recargo import erp_cents
from costs.store import get as get_cost

MFA_MAX_AGE = timedelta(minutes=5)
OPEN_STATES = ("pending_review", "pending_link", "approved_by_buyer", "sent", "retrying", "failed")
TRIGGERS = ("missing_cost", "order_confirmed", "receipt_matched", "buyer_entry")


class WriteError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class WriteRequestResult:
    request: Row[Any] | None
    status: str                       # the request status, or "unchanged" / "not_applicable" when none was created
    warnings: list[str] = field(default_factory=list)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _link(conn: Connection, product_id: int, supplier_id: str) -> Row[Any] | None:
    return conn.execute(select(erp_supplier_links).where(erp_supplier_links.c.product_id == product_id, erp_supplier_links.c.supplier_id == supplier_id)).first()


def _previous_erp_value(conn: Connection, product_id: int, supplier_id: str) -> Decimal | None:
    row = conn.execute(select(supplier_costs.c.cost_with_recargo).where(
        supplier_costs.c.product_id == product_id, supplier_costs.c.supplier_id == supplier_id, supplier_costs.c.variant_id.is_(None),
        supplier_costs.c.source == "siweb_product_supplier").order_by(supplier_costs.c.version.desc()).limit(1)).first()
    return None if row is None else Decimal(str(row.cost_with_recargo))


def _variant_conflict(conn: Connection, product_id: int, variant_id: int | None) -> bool:
    """The ERP stores one cost per product-supplier. A variant-specific cost, or a product with several variants, may not
    be what the ERP record means; the buyer has to acknowledge that before release."""
    if variant_id is not None:
        return True
    n = conn.execute(select(func.count()).select_from(product_refs).where(product_refs.c.product_id == product_id)).scalar_one()
    return bool(n > 1)


def request_write(conn: Connection, cost_id: str, trigger: str, actor: str, now: datetime | None = None, *, median_lot_refs: list[dict[str, Any]] | None = None,
                  median_cost: Decimal | None = None, margin: Evaluation | None = None) -> WriteRequestResult:
    if trigger not in TRIGGERS:
        raise WriteError("invalid_trigger")
    now = now or datetime.now(UTC)
    cost = get_cost(conn, cost_id)
    if cost.superseded_by is not None:
        raise WriteError("cost_superseded")
    link = _link(conn, cost.product_id, cost.supplier_id)
    if trigger == "missing_cost" and link is not None and link.has_cost:
        raise WriteError("erp_already_has_cost")
    proposed = Decimal(str(cost.cost_with_recargo))
    previous = _previous_erp_value(conn, cost.product_id, cost.supplier_id)
    if link is not None and link.has_cost and previous is not None and erp_cents(previous) == erp_cents(proposed):
        return WriteRequestResult(None, "unchanged")
    key = f"{cost.product_id}:{cost.supplier_id}:{cost.version}:{cost.variant_id or 0}:{trigger}"
    existing = conn.execute(select(cost_write_requests).where(cost_write_requests.c.idempotency_key == key)).first()
    warnings = ["variant_conflict"] if _variant_conflict(conn, cost.product_id, cost.variant_id) else []
    if existing is not None:
        return WriteRequestResult(existing, existing.status, warnings)
    status = "pending_link" if link is None else "pending_review"
    rid = str(uuid.uuid4())
    conn.execute(insert(cost_write_requests).values(
        id=rid, cost_id=cost_id, product_id=cost.product_id, supplier_id=cost.supplier_id, trigger=trigger, proposed_value=proposed,
        previous_siweb_value=previous, status=status, attempts=0, requested_by=actor, idempotency_key=key, created_at=now, updated_at=now,
        median_cost=median_cost if median_cost is not None else proposed, median_lot_refs=median_lot_refs,
        pvp_used=None if margin is None else margin.pvp, pvp_age_days=None if margin is None else margin.pvp_age_days, margin_before=None if margin is None else margin.margin_before,
        margin_after=None if margin is None else margin.margin_after, rule_flags=[] if margin is None else list(margin.flags)))
    audit(conn, actor, "cost_write.requested", "cost_write", rid, after={"status": status, "trigger": trigger, "cents": erp_cents(proposed)}, now=now)
    return WriteRequestResult(conn.execute(select(cost_write_requests).where(cost_write_requests.c.id == rid)).one(), status, warnings)


def _req(conn: Connection, request_id: str) -> Row[Any]:
    r = conn.execute(select(cost_write_requests).where(cost_write_requests.c.id == request_id)).first()
    if r is None:
        raise WriteError("unknown_request")
    return r


def approve_write(conn: Connection, request_id: str, principal: Principal, writer: BlobWriter, acknowledge_variant_conflict: bool = False,
                  now: datetime | None = None) -> Row[Any]:
    now = now or datetime.now(UTC)
    if "buyer" not in principal.roles:
        raise WriteError("not_a_buyer")
    if principal.auth_time is None or not principal.mfa_fresh(MFA_MAX_AGE, now):
        raise WriteError("mfa_required")
    r = _req(conn, request_id)
    if r.status not in ("pending_review", "pending_link", "failed"):
        raise WriteError(f"cannot_release_from_{r.status}")
    overridden = r.override_value is not None
    expected = r.override_value if overridden else r.median_cost
    if expected is None or Decimal(str(expected)) != Decimal(str(r.proposed_value)):
        raise WriteError("median_required")          # the released value is the median of the lot costs, or the admin's override (FR-042/044)
    if overridden and r.override_by == principal.subject:
        raise WriteError("override_release_same_person")   # whoever set the override cannot release it (FR-044)
    if BELOW_MINIMUM in (r.rule_flags or []) and not overridden:
        raise WriteError("margin_below_minimum")           # blocked until an admin override (FR-043 d)
    if UNAVAILABLE in (r.rule_flags or []) and not overridden:
        raise WriteError("margin_unavailable")             # no price, no margin: blocked until the price is known or an admin overrides
    cost = get_cost(conn, r.cost_id)
    if cost.superseded_by is not None:
        raise WriteError("cost_superseded")
    if _link(conn, r.product_id, r.supplier_id) is None:
        raise WriteError("pending_link")          # no ERP record: no request is made until the buyer creates the link
    if _variant_conflict(conn, r.product_id, cost.variant_id) and not acknowledge_variant_conflict:
        raise WriteError("variant_conflict_unacknowledged")
    conn.execute(update(cost_write_requests).where(cost_write_requests.c.id == request_id).values(
        status="approved_by_buyer", reviewed_by=principal.subject, released_by=principal.subject, updated_at=now, last_error=None))
    audit(conn, principal.subject, "cost_write.approved", "cost_write", request_id, before={"status": r.status}, after={"status": "approved_by_buyer"}, now=now)
    publish(conn, writer, WRITE_REQUESTED, request_id, {"cost_write_request_id": request_id}, get_correlation_id() or set_correlation_id())
    return _req(conn, request_id)


def cancel_write(conn: Connection, request_id: str, actor: str, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    r = _req(conn, request_id)
    if r.status in ("succeeded", "cancelled", "sent"):
        raise WriteError(f"cannot_cancel_from_{r.status}")
    conn.execute(update(cost_write_requests).where(cost_write_requests.c.id == request_id).values(status="cancelled", updated_at=now))
    audit(conn, actor, "cost_write.cancelled", "cost_write", request_id, before={"status": r.status}, after={"status": "cancelled"}, now=now)


def list_visible(conn: Connection) -> list[Row[Any]]:
    """Requests stay visible until they succeed or are cancelled, failures included."""
    return list(conn.execute(select(cost_write_requests).where(cost_write_requests.c.status.in_(OPEN_STATES)).order_by(cost_write_requests.c.created_at)).all())


def writer_view(conn: Connection, request_id: str) -> dict[str, Any] | None:
    """What the writer may act on: only a request the buyer released. Anything else returns None (and is refused)."""
    r = conn.execute(select(cost_write_requests).where(cost_write_requests.c.id == request_id)).first()
    if r is None or r.status not in ("approved_by_buyer", "sent", "retrying"):
        return None
    return {"id": r.id, "status": r.status, "product_id": r.product_id, "supplier_id": r.supplier_id, "cents": erp_cents(Decimal(str(r.proposed_value))),
            "previous_cents": None if r.previous_siweb_value is None else erp_cents(Decimal(str(r.previous_siweb_value))), "idempotency_key": r.idempotency_key,
            "supplier_contact_id": _contact_id(conn, r.supplier_id)}


def _contact_id(conn: Connection, supplier_id: str) -> int | None:
    from db.tables import suppliers

    row = conn.execute(select(suppliers.c.external_contact_id).where(suppliers.c.id == supplier_id)).first()
    return None if row is None else row.external_contact_id


def apply_outcome(conn: Connection, request_id: str, outcome: str, attempts: int, error: str | None = None, now: datetime | None = None) -> Row[Any]:
    """Records what the writer reported (siweb.cost.write_completed.v1). Outcomes: sent / succeeded / retrying / failed / pending_link."""
    if outcome not in ("sent", "succeeded", "retrying", "failed", "pending_link"):
        raise WriteError("invalid_outcome")
    now = now or datetime.now(UTC)
    r = _req(conn, request_id)
    if r.status in ("succeeded", "cancelled"):
        return r                                   # late or duplicate report: never regress a final state
    conn.execute(update(cost_write_requests).where(cost_write_requests.c.id == request_id).values(
        status=outcome, attempts=max(attempts, r.attempts), last_error=(error or None) and str(error)[:200], updated_at=now))
    if outcome == "succeeded":
        conn.execute(update(erp_supplier_links).where(erp_supplier_links.c.product_id == r.product_id, erp_supplier_links.c.supplier_id == r.supplier_id)
                     .values(has_cost=True, last_seen_at=now))
    audit(conn, "siweb-cost-writer", f"cost_write.{outcome}", "cost_write", request_id, before={"status": r.status}, after={"status": outcome, "attempts": attempts}, now=now)
    return _req(conn, request_id)


def relink_pending(conn: Connection, product_id: int, supplier_id: str, now: datetime | None = None) -> int:
    """Called when the ERP import sees a link that did not exist: parked requests become reviewable again (not released)."""
    now = now or datetime.now(UTC)
    res = conn.execute(update(cost_write_requests).where(
        cost_write_requests.c.product_id == product_id, cost_write_requests.c.supplier_id == supplier_id, cost_write_requests.c.status == "pending_link")
        .values(status="pending_review", updated_at=now))
    return int(res.rowcount)


OVERRIDE_REASON_MIN = 5


def set_override(conn: Connection, request_id: str, principal: Principal, value: Decimal, reason: str, now: datetime | None = None) -> Row[Any]:
    """An admin replaces the median with their own value for a blocked or flagged update (FR-044). Nothing is released here:
    the buyer review, a different releaser, fresh MFA and the writer's own checks all still apply."""
    now = now or datetime.now(UTC)
    if "admin" not in principal.roles:
        raise WriteError("not_an_admin")
    if isinstance(value, float):
        raise TypeError("floats are not allowed for money")
    if value < 0:
        raise WriteError("negative_value")
    reason = (reason or "").strip()
    if len(reason) < OVERRIDE_REASON_MIN or len(reason) > 500:
        raise WriteError("override_reason_required")
    r = _req(conn, request_id)
    if r.status not in ("pending_review", "pending_link", "failed"):
        raise WriteError(f"cannot_override_from_{r.status}")
    flags = [f for f in (r.rule_flags or []) if f != "override"]
    margin_after = r.margin_after
    if r.pvp_used is not None:
        ev = evaluate(value, None if r.previous_siweb_value is None else Decimal(str(r.previous_siweb_value)), Decimal(str(r.pvp_used)))
        flags = [f for f in ev.flags if f != BELOW_MINIMUM] + ([f"override_{BELOW_MINIMUM}"] if ev.blocked else [])
        margin_after = ev.margin_after
    flags.append("override")
    conn.execute(update(cost_write_requests).where(cost_write_requests.c.id == request_id).values(
        override_value=value.quantize(Decimal("0.0001")), override_reason=reason, override_by=principal.subject, override_at=now, proposed_value=value.quantize(Decimal("0.0001")),
        margin_after=margin_after, rule_flags=flags, updated_at=now))
    audit(conn, principal.subject, "cost_write.override_set", "cost_write", request_id,
          before={"median_cost": None if r.median_cost is None else str(r.median_cost), "margin_after": None if r.margin_after is None else str(r.margin_after)},
          after={"override_value": str(value), "reason": reason, "margin_before": None if r.margin_before is None else str(r.margin_before),
                 "margin_after": None if margin_after is None else str(margin_after), "set_by": principal.subject, "at": now.isoformat()}, now=now)
    return _req(conn, request_id)


def awaiting_other_buyer(conn: Connection, request_id: str) -> bool:
    """True when an override is set and no active buyer other than its author exists to release it (the override stays pending)."""
    from db.tables import user_roles

    r = _req(conn, request_id)
    if r.override_by is None:
        return False
    for u in conn.execute(select(user_roles.c.user_id, user_roles.c.roles, user_roles.c.active)).all():
        if u.active and u.user_id != r.override_by and "buyer" in (u.roles or []):
            return False
    return True
