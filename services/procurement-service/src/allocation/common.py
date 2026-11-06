"""Shared allocation types: candidate (variant, supplier) pairs, chosen lines, supplier groups."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from proposals.model import Discount, Offer, ProposalInputs, SupplierTermsIn, ticks
from proposals.targets import Target, compute_target


@dataclass(frozen=True)
class Cand:
    variant_id: int
    supplier_id: str
    qty: int
    unit_ticks: int
    line_ticks: int
    lead: int
    risk_ticks: int
    offer: Offer
    target: Target


@dataclass(frozen=True)
class LineSpec:
    variant_id: int
    mandatory: bool               # False => top-up candidate (needed soon), taken only if it pays off
    cands: tuple[Cand, ...]
    fixed_supplier: str | None = None
    fixed_qty: int | None = None
    rejected: tuple[tuple[str, str], ...] = ()   # (supplier_id, reason) for offers that were not eligible


@dataclass(frozen=True)
class Chosen:
    variant_id: int
    supplier_id: str
    qty: int
    unit_ticks: int
    line_ticks: int
    lead: int
    topup: bool


@dataclass(frozen=True)
class Group:
    supplier_id: str
    subtotal_ticks: int
    delivery_charge_ticks: int
    total_ticks: int
    qty: int
    minimum_status: str                         # met / shortfall
    shortfall_value_ticks: int = 0
    shortfall_qty: int = 0
    free_delivery: bool = False
    discount_ticks: int = 0


@dataclass
class Allocation:
    chosen: list[Chosen]
    groups: list[Group]
    solver_status: str
    total_ticks: int
    over_budget_ticks: int = 0
    notes: list[str] = field(default_factory=list)


def percent_basis_points(value: Decimal) -> int:
    return int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))


def threshold_units(d: Discount) -> int:
    return math.ceil(d.threshold)


def discount_ticks_for(d: Discount, sub_ticks: int) -> int:
    """What one tier takes off a subtotal (never more than the subtotal)."""
    if d.kind == "percent":
        return sub_ticks * percent_basis_points(d.value) // 10_000
    return min(ticks(d.value), sub_ticks)


def best_discount_ticks(t: SupplierTermsIn, sub_ticks: int, qty: int) -> int:
    """The best qualifying tier applies. Thresholds are judged on the list subtotal and the units, before any discount."""
    best = 0
    for d in t.discounts:
        met = sub_ticks >= ticks(d.threshold) if d.basis == "order_value" else qty >= threshold_units(d)
        if met:
            best = max(best, discount_ticks_for(d, sub_ticks))
    return best


def round_up(qty: int, pack: int) -> int:
    pack = max(pack, 1)
    return -(-qty // pack) * pack


def build_lines(inputs: ProposalInputs) -> list[LineSpec]:
    lines: list[LineSpec] = []
    ov = inputs.overrides
    for v in sorted(inputs.variants, key=lambda x: x.variant_id):
        usable: list[Offer] = []
        rejected: list[tuple[str, str]] = []
        for o in sorted(v.offers, key=lambda o: o.supplier_id):
            if o.cost_status == "blocked_jump":
                rejected.append((o.supplier_id, "cost_blocked"))
            elif o.lead_time_days > inputs.max_lead_days:
                rejected.append((o.supplier_id, "lead_time_too_long"))
            elif o.supplier_id in ov.excluded.get(v.variant_id, frozenset()):
                rejected.append((o.supplier_id, "excluded_by_buyer"))
            elif inputs.suppliers.get(o.supplier_id, SupplierTermsIn(o.supplier_id)).disabled:
                rejected.append((o.supplier_id, "supplier_disabled"))
            else:
                usable.append(o)
        if not usable:
            if v.offers or ov.fixed_qty.get(v.variant_id):
                lines.append(LineSpec(v.variant_id, True, (), rejected=tuple(rejected)))
            continue
        fastest = min(o.lead_time_days for o in usable)
        base_need = compute_target(v, fastest).need
        fixed_qty = ov.fixed_qty.get(v.variant_id)
        mandatory = base_need > 0 or bool(fixed_qty)
        soon = v.soon_need if not mandatory else 0
        if not mandatory and soon <= 0:
            continue
        cands: list[Cand] = []
        for o in usable:
            tgt = compute_target(v, o.lead_time_days)
            want = fixed_qty if fixed_qty else (max(tgt.need, o.min_order_qty) if mandatory else max(soon, o.min_order_qty))
            qty = round_up(want, o.pack_size) if not fixed_qty else fixed_qty
            if qty <= 0:
                continue
            unit = ticks(o.unit_cost)
            risk = (o.lead_time_days - fastest) * inputs.risk_penalty_ticks_per_unit_day * qty
            preferred = o.preferred if o.preferred is not None else inputs.suppliers.get(o.supplier_id, SupplierTermsIn(o.supplier_id)).preferred
            risk -= 1 if preferred else 0          # a preferred supplier wins a tie, and only a tie (1 tick = 0.0001 EUR)
            cands.append(Cand(v.variant_id, o.supplier_id, qty, unit, unit * qty, o.lead_time_days, risk, o, tgt))
        lines.append(LineSpec(v.variant_id, mandatory, tuple(cands), ov.fixed_supplier.get(v.variant_id), fixed_qty, tuple(rejected)))
    return lines


def summarise(chosen: list[Chosen], suppliers: dict[str, SupplierTermsIn]) -> list[Group]:
    by: dict[str, list[Chosen]] = {}
    for c in chosen:
        by.setdefault(c.supplier_id, []).append(c)
    groups = []
    for sid in sorted(by):
        t = suppliers.get(sid, SupplierTermsIn(sid))
        sub = sum(c.line_ticks for c in by[sid])
        qty = sum(c.qty for c in by[sid])
        free = t.free_delivery_threshold is not None and sub >= ticks(t.free_delivery_threshold)
        charge = 0 if free or t.delivery_charge is None else ticks(t.delivery_charge)
        short_v = max(ticks(t.min_order_value) - sub, 0) if t.min_order_value is not None else 0
        short_q = max((t.min_qty_for_delivery or 0) - qty, 0)
        disc = best_discount_ticks(t, sub, qty)
        groups.append(Group(sid, sub, charge, sub - disc + charge, qty, "shortfall" if short_v or short_q else "met", short_v, short_q, free, disc))
    return groups


def budget_excess(groups: list[Group], budget: Decimal | None) -> int:
    return 0 if budget is None else max(sum(g.total_ticks for g in groups) - ticks(budget), 0)
