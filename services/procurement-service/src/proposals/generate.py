"""T095: weekly proposal generation. A pure function of ProposalInputs plus rule versions; storing is separate.

Every line carries a structured explanation (rendered to es-ES by the UI): policy, service level, horizon, targets,
stock position, the supplier chosen and the alternatives compared, constraints applied, risk and confidence. The inputs
hash covers everything the result depends on, so the same inputs and rule versions regenerate an identical proposal.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from allocation.common import Allocation, Cand, Chosen, Group, LineSpec, build_lines
from allocation.cpsat import allocate_cpsat
from allocation.greedy import allocate_greedy
from allocation.shortfall import ShortfallOption, options_for
from audit.chain import append as audit
from db.tables import proposal_lines, proposals, replenishment_targets, supplier_order_groups
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection
from terms.schedule import delivery_date

from proposals.model import RULES_VERSION, Offer, ProposalInputs, SupplierTermsIn, inputs_hash, money
from proposals.targets import Target

RULE_VERSIONS = {"targets": RULES_VERSION, "allocation": RULES_VERSION, "explanation": RULES_VERSION, "solver": "cp-sat"}
NAMESPACE = uuid.UUID("5c1e3c6e-7a41-4d7e-9a43-1d2e7b9c0a11")


class ProposalConflictError(Exception):
    code = "proposal_conflict"


@dataclass(frozen=True)
class DraftLine:
    variant_id: int
    product_id: int
    supplier_id: str
    qty: int
    unit_cost: Decimal
    line_total: Decimal
    policy: str
    safety_stock: int | None
    constraints: tuple[str, ...]
    risk: str
    confidence: str
    explanation: dict[str, Any]
    alternatives: tuple[dict[str, Any], ...]
    topup: bool


@dataclass(frozen=True)
class DraftGroup:
    supplier_id: str
    subtotal: Decimal
    delivery_charge: Decimal
    total: Decimal
    expected_delivery: date
    minimum_status: str
    free_delivery: bool
    options: tuple[dict[str, Any], ...]
    discount: Decimal = Decimal(0)


@dataclass(frozen=True)
class Draft:
    lines: tuple[DraftLine, ...]
    groups: tuple[DraftGroup, ...]
    targets: tuple[Target, ...]
    solver_status: str
    inputs_hash: str
    rule_versions: dict[str, str]
    greedy_total: Decimal
    optimized_total: Decimal
    over_budget: Decimal
    notes: tuple[str, ...] = field(default_factory=tuple)
    terms_versions: dict[str, Any] = field(default_factory=dict)
    policy_versions: dict[str, Any] = field(default_factory=dict)
    forecast_run_id: str | None = None
    dataset_version_id: str | None = None


def _risk(t: Target, shortfall: bool) -> str:
    if shortfall or t.inventory_position <= 0:
        return "high"
    return "medium" if t.reorder_point and t.inventory_position < t.reorder_point / 2 else "low"


def _confidence(t: Target, cost_status: str, topup: bool) -> str:
    if t.fallback:
        return "low"
    return "medium" if cost_status != "ok" or topup else "high"


def _terms_explanation(offer: Offer, group: Group) -> dict[str, Any]:
    """Which saved terms produced this line's values (FR-014): versions, where each value came from, conflicts with the ERP, discount."""
    info = dict(offer.terms_info)
    return {"supplier_version": info.get("supplier_version"), "override_version": info.get("override_version"),
            "sources": dict(info.get("sources", ())), "conflicts": [dict(c) for c in info.get("conflicts", ())],
            "preferred": offer.preferred, "supplier_discount": str(money(group.discount_ticks)),
            **({"fx": dict(info["fx"])} if "fx" in info else {})}      # MMI-6: the exchange rate behind a converted cost (currency, original cost, rate, day)


def _won_on_preference(line: LineSpec, chosen: Chosen, inputs: ProposalInputs) -> bool:
    """MMI-6 FR-019: the chosen supplier is preferred and another offer cost exactly the same with the same lead time (a preference only breaks ties)."""
    mine = next(x for x in line.cands if x.supplier_id == chosen.supplier_id)
    preferred = mine.offer.preferred if mine.offer.preferred is not None else inputs.suppliers.get(chosen.supplier_id, SupplierTermsIn(chosen.supplier_id)).preferred
    return bool(preferred) and any(x.supplier_id != chosen.supplier_id and x.line_ticks == mine.line_ticks and x.lead == mine.lead for x in line.cands)


def _reason(line: LineSpec, chosen: Chosen, greedy: dict[int, Chosen], group: Group, inputs: ProposalInputs, plan_costs_more: bool = False) -> str:
    if line.fixed_supplier == chosen.supplier_id:
        return "buyer_override"
    if len(line.cands) == 1:
        return "only_option"
    if chosen.topup:
        return "top_up_for_supplier_minimum_or_free_delivery"
    g = greedy.get(chosen.variant_id)
    if g is not None and g.supplier_id != chosen.supplier_id:
        risk = {c.supplier_id: c.risk_ticks for c in line.cands}
        if plan_costs_more and risk.get(g.supplier_id, 0) > risk.get(chosen.supplier_id, 0):
            return "lower_lead_time_risk"          # the optimum paid a little more cash to avoid a slower supplier, so it must not say "lower total"
        return "lower_total_with_supplier_terms"
    if _won_on_preference(line, chosen, inputs):
        return "preferred_supplier_on_tie"
    return "free_delivery_threshold_reached" if group.free_delivery else "lowest_cost"


def generate(inputs: ProposalInputs, time_limit_s: float = 30.0, seed: int = 1) -> Draft:
    lines = build_lines(inputs)
    greedy = allocate_greedy(inputs, lines)
    alloc: Allocation = allocate_cpsat(inputs, lines, time_limit_s, seed)
    options: list[ShortfallOption] = options_for(inputs, lines, alloc)
    by_variant = {v.variant_id: v for v in inputs.variants}
    spec = {ln.variant_id: ln for ln in lines}
    greedy_by = {c.variant_id: c for c in greedy.chosen}
    groups = {g.supplier_id: g for g in alloc.groups}
    max_lead = {sid: max((c.lead for c in alloc.chosen if c.supplier_id == sid), default=0) for sid in groups}
    out_lines: list[DraftLine] = []
    targets: list[Target] = []
    for c in sorted(alloc.chosen, key=lambda c: c.variant_id):
        ln, v = spec[c.variant_id], by_variant[c.variant_id]
        cand: Cand = next(x for x in ln.cands if x.supplier_id == c.supplier_id)
        t, g = cand.target, groups[c.supplier_id]
        targets.append(t)
        constraints: list[str] = []
        if cand.offer.pack_size > 1 and c.qty > t.need:
            constraints.append("pack_multiple")
        if cand.offer.min_order_qty and c.qty == cand.offer.min_order_qty and t.need < cand.offer.min_order_qty:
            constraints.append("min_order_qty")
        if t.expiring_qty:
            constraints.append("expiring_lots")
        if g.minimum_status == "shortfall":
            constraints.append("supplier_minimum_shortfall")
        if alloc.over_budget_ticks:
            constraints.append("over_budget")
        if cand.lead > 7:
            constraints.append("lead_time")
        alternatives = tuple(
            {"supplier_id": x.supplier_id, "unit_cost": str(money(x.unit_ticks)), "qty": x.qty, "line_total": str(money(x.line_ticks)),
             "lead_time_days": x.lead, "chosen": x.supplier_id == c.supplier_id} for x in ln.cands)
        explanation = {
            "version": 1, "policy": t.policy, "forecast_eligible": not t.fallback, "forecast_basis": "imported_estimates" if t.estimate_based else "actual_demand", "service_level": str(t.service_level),
            "horizon_days": t.horizon_days, "expected_demand": t.expected_demand, "safety_stock": t.safety_stock, "order_up_to": t.order_up_to,
            "reorder_point": t.reorder_point,
            "position": {"on_hand": t.on_hand, "expiring": t.expiring_qty, "usable": t.usable_on_hand, "inbound": t.inbound_counted, "total": t.inventory_position},
            "need": t.need, "top_up": c.topup, "clinical_critical": v.clinical_critical,
            "supplier": {"chosen": c.supplier_id, "reason": _reason(ln, c, greedy_by, g, inputs, alloc.total_ticks > greedy.total_ticks), "alternatives": list(alternatives),
                         "rejected": [{"supplier_id": s, "reason": r} for s, r in ln.rejected]},
            "cost": {"unit": str(money(c.unit_ticks)), "source": cand.offer.source, "status": cand.offer.cost_status, "cost_id": cand.offer.cost_id},
            "constraints": constraints,
            "terms": {**_terms_explanation(cand.offer, g), "expected_delivery_date": _expected_delivery(inputs, c.supplier_id, max_lead[c.supplier_id]).isoformat()},
            "floor_reason": t.floor_reason, "policy_applied": {k: v2 for k, v2 in v.policy_info},
        }
        out_lines.append(DraftLine(
            c.variant_id, v.product_id, c.supplier_id, c.qty, money(c.unit_ticks), money(c.line_ticks), t.policy, t.safety_stock, tuple(constraints),
            _risk(t, g.minimum_status == "shortfall"), _confidence(t, cand.offer.cost_status, c.topup), explanation, alternatives, c.topup))
    opts_by_supplier: dict[str, list[dict[str, Any]]] = {}
    for o in options:
        opts_by_supplier.setdefault(o.supplier_id, []).append({"kind": o.kind, "cost_delta": str(money(o.cost_delta_ticks)), "detail": o.detail})
    out_groups = tuple(DraftGroup(
        g.supplier_id, money(g.subtotal_ticks), money(g.delivery_charge_ticks), money(g.total_ticks), _expected_delivery(inputs, g.supplier_id, max_lead[g.supplier_id]),
        g.minimum_status, g.free_delivery, tuple(opts_by_supplier.get(g.supplier_id, ())), money(g.discount_ticks)) for g in alloc.groups)
    return Draft(tuple(out_lines), out_groups, tuple(targets), alloc.solver_status, inputs_hash(inputs, RULE_VERSIONS), dict(RULE_VERSIONS),
                 money(greedy.total_ticks), money(alloc.total_ticks), money(alloc.over_budget_ticks), tuple(alloc.notes), dict(inputs.terms_versions), dict(inputs.policy_versions), inputs.forecast_run_id, inputs.dataset_version_id)


def _expected_delivery(inputs: ProposalInputs, supplier_id: str, lead_days: int) -> date:
    """MMI-6 FR-020: the first order day the supplier accepts (cutoff applied) plus the longest lead time, on the supplier's delivery weekdays.

    A supplier with no schedule rules keeps the old meaning: today plus the lead time.
    """
    t = inputs.suppliers.get(supplier_id)
    return delivery_date(t.next_order_date if t is not None and t.next_order_date is not None else inputs.today, lead_days,
                         t.delivery_weekdays if t is not None else ())


def store(conn: Connection, draft: Draft, created_by: str, week: str, budget: Decimal | None = None, now: datetime | None = None) -> str:
    """Persist a draft. Same week and inputs -> the existing proposal; an approved/exported week is never overwritten."""
    now = now or datetime.now(UTC)
    existing = conn.execute(select(proposals).where(proposals.c.week == week, proposals.c.status != "superseded")).all()
    for p in existing:
        if p.inputs_hash == draft.inputs_hash:
            return str(p.id)
    if any(p.status in ("approved", "exported") for p in existing):
        raise ProposalConflictError("this week already has an approved proposal")
    pid = str(uuid.uuid5(NAMESPACE, f"{week}:{draft.inputs_hash}"))
    for p in existing:
        conn.execute(update(proposals).where(proposals.c.id == p.id).values(status="superseded", updated_at=now))
        audit(conn, created_by, "proposal.superseded", "proposal", str(p.id), before={"status": p.status}, after={"by": pid}, now=now)
    conn.execute(insert(proposals).values(
        id=pid, week=week, status="draft", created_by=created_by, last_edited_by=created_by, version=1, inputs_hash=draft.inputs_hash,
        rule_versions=draft.rule_versions, solver_status=draft.solver_status, budget=budget, created_at=now, updated_at=now,
        terms_version_ids=draft.terms_versions or None, policy_version_ids=draft.policy_versions or None,
        dataset_version_id=draft.dataset_version_id, forecast_run_id=draft.forecast_run_id,
        flags={"greedy_total": str(draft.greedy_total), "optimized_total": str(draft.optimized_total), "over_budget": str(draft.over_budget), "notes": list(draft.notes)}))
    for ln in draft.lines:
        conn.execute(insert(proposal_lines).values(
            id=str(uuid.uuid5(NAMESPACE, f"{pid}:{ln.variant_id}")), proposal_id=pid, variant_id=ln.variant_id, product_id=ln.product_id, supplier_id=ln.supplier_id,
            qty=ln.qty, unit_cost_with_recargo=ln.unit_cost, line_total=ln.line_total, forecast_or_policy=ln.policy, safety_stock=ln.safety_stock,
            constraints_applied=list(ln.constraints), risk=ln.risk, confidence=ln.confidence, explanation=ln.explanation,
            alternatives_compared=list(ln.alternatives), manual_override=False, topup=ln.topup))
    for t in draft.targets:
        conn.execute(insert(replenishment_targets).values(
            proposal_id=pid, variant_id=t.variant_id, protection_horizon_days=t.horizon_days, expected_demand=t.expected_demand, safety_stock=t.safety_stock,
            target_level=t.order_up_to, inventory_position=t.inventory_position, inputs_hash=draft.inputs_hash))
    for g in draft.groups:
        conn.execute(insert(supplier_order_groups).values(
            proposal_id=pid, supplier_id=g.supplier_id, subtotal=g.subtotal, delivery_charge=g.delivery_charge, total_cost=g.total, expected_delivery_date=g.expected_delivery,
            minimum_status=g.minimum_status, free_delivery=g.free_delivery, shortfall_options=list(g.options), discount=g.discount))
    audit(conn, created_by, "proposal.generated", "proposal", pid, after={"week": week, "lines": len(draft.lines), "inputs_hash": draft.inputs_hash}, now=now)
    return pid
