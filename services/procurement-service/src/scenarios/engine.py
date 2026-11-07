"""T142: what-if scenarios. A scenario is a set of changes applied to a copy of the current proposal inputs; the same allocation engine solves it.

Nothing here touches a database or the ERP: ``apply_params`` and ``solve`` are pure functions of their arguments, so the same inputs, the same
parameters and the same rules give the same result (recorded as a hash). Every change that moves an allocation gets a stated reason.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any

from proposals.generate import RULE_VERSIONS, Draft, generate
from proposals.model import ProposalInputs, SupplierTermsIn, VariantInput, canonical

MAX_SUPPLIER_DELTAS = 50
MIN_LEVEL, MAX_LEVEL = Decimal("0.5"), Decimal("0.9999")
DELTA_FIELDS = ("min_order_value", "delivery_charge", "free_delivery_threshold", "lead_time_days", "pack_multiple", "min_order_qty")
SENSITIVITY_TOP = 3
SENSITIVITY_STEP = Decimal("0.10")
SENSITIVITY_SECONDS = 5.0


class ScenarioError(Exception):
    def __init__(self, message: str, code: str = "scenario_invalid") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SupplierDelta:
    min_order_value: Decimal | None = None
    delivery_charge: Decimal | None = None
    free_delivery_threshold: Decimal | None = None
    lead_time_days: int | None = None
    pack_multiple: int | None = None
    min_order_qty: int | None = None


@dataclass(frozen=True)
class ScenarioParams:
    budget: Decimal | None = None
    disabled_suppliers: tuple[str, ...] = ()
    supplier_deltas: dict[str, SupplierDelta] = field(default_factory=dict)
    service_level_delta: Decimal = Decimal(0)

    def validate(self) -> None:
        for v in (self.budget, self.service_level_delta):
            if isinstance(v, float):
                raise ScenarioError("floats are not allowed")
        if self.budget is not None and self.budget < 0:
            raise ScenarioError("budget must not be negative")
        if not (Decimal("-0.4") <= self.service_level_delta <= Decimal("0.4")):
            raise ScenarioError("service level change out of range")
        if len(self.supplier_deltas) > MAX_SUPPLIER_DELTAS:
            raise ScenarioError("too many supplier changes")
        for d in self.supplier_deltas.values():
            for name in ("min_order_value", "delivery_charge", "free_delivery_threshold"):
                v = getattr(d, name)
                if v is not None and (isinstance(v, float) or v < 0):
                    raise ScenarioError(f"{name} out of range")
            for name in ("lead_time_days", "pack_multiple", "min_order_qty"):
                v = getattr(d, name)
                if v is not None and not (0 <= v <= 365 if name != "pack_multiple" else 1 <= v <= 10_000):
                    raise ScenarioError(f"{name} out of range")
            if d.min_order_value is not None and d.free_delivery_threshold is not None and d.free_delivery_threshold < d.min_order_value:
                raise ScenarioError("threshold below minimum")

    def is_empty(self) -> bool:
        return self.budget is None and not self.disabled_suppliers and not self.supplier_deltas and self.service_level_delta == 0

    def to_json(self) -> dict[str, Any]:
        return {"budget": None if self.budget is None else str(self.budget), "disabled_suppliers": sorted(self.disabled_suppliers),
                "supplier_deltas": {sid: {k: (None if v is None else str(v)) for k, v in vars(d).items() if v is not None} for sid, d in sorted(self.supplier_deltas.items())},
                "service_level_delta": str(self.service_level_delta)}

    @staticmethod
    def from_json(doc: dict[str, Any]) -> ScenarioParams:
        def dec(v: Any) -> Decimal | None:
            return None if v is None else Decimal(str(v))

        def num(v: Any) -> int | None:
            return None if v is None else int(v)

        try:
            deltas = {sid: SupplierDelta(dec(d.get("min_order_value")), dec(d.get("delivery_charge")), dec(d.get("free_delivery_threshold")), num(d.get("lead_time_days")),
                                         num(d.get("pack_multiple")), num(d.get("min_order_qty"))) for sid, d in (doc.get("supplier_deltas") or {}).items()}
            p = ScenarioParams(dec(doc.get("budget")), tuple(doc.get("disabled_suppliers") or ()), deltas, dec(doc.get("service_level_delta")) or Decimal(0))
        except (ValueError, ArithmeticError, TypeError, AttributeError) as exc:
            raise ScenarioError("malformed parameters") from exc
        p.validate()
        return p


def apply_params(base: ProposalInputs, p: ScenarioParams) -> ProposalInputs:
    """A modified copy of the inputs; the originals are frozen dataclasses and are never touched."""
    p.validate()
    disabled = set(p.disabled_suppliers)
    variants: list[VariantInput] = []
    for v in base.variants:
        offers = []
        for o in v.offers:
            if o.supplier_id in disabled:
                continue
            d = p.supplier_deltas.get(o.supplier_id)
            if d is not None:
                o = replace(o, lead_time_days=o.lead_time_days if d.lead_time_days is None else d.lead_time_days, pack_size=o.pack_size if d.pack_multiple is None else d.pack_multiple,
                            min_order_qty=o.min_order_qty if d.min_order_qty is None else d.min_order_qty)
            offers.append(o)
        level = min(max(v.service_level + p.service_level_delta, MIN_LEVEL), MAX_LEVEL) if p.service_level_delta else v.service_level
        variants.append(replace(v, offers=tuple(offers), service_level=level))
    terms: dict[str, SupplierTermsIn] = {}
    for sid, t in base.suppliers.items():
        d = p.supplier_deltas.get(sid)
        terms[sid] = t if d is None else replace(t, min_order_value=t.min_order_value if d.min_order_value is None else d.min_order_value,
                                                 delivery_charge=t.delivery_charge if d.delivery_charge is None else d.delivery_charge,
                                                 free_delivery_threshold=t.free_delivery_threshold if d.free_delivery_threshold is None else d.free_delivery_threshold)
    return replace(base, variants=tuple(variants), suppliers=terms, budget=base.budget if p.budget is None else p.budget)


def solve(inputs: ProposalInputs, time_limit_s: float = 20.0) -> Draft:
    return generate(inputs, time_limit_s)


def result_hash(draft: Draft) -> str:
    body = {"lines": [(ln.variant_id, ln.supplier_id, ln.qty, str(ln.unit_cost)) for ln in draft.lines],
            "groups": [(g.supplier_id, str(g.subtotal), str(g.delivery_charge), str(g.discount), g.minimum_status, g.free_delivery) for g in draft.groups], "over_budget": str(draft.over_budget)}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def input_fingerprint(base: ProposalInputs) -> str:
    return hashlib.sha256((canonical(base) + json.dumps(RULE_VERSIONS, sort_keys=True)).encode()).hexdigest()


def explain_changes(base_draft: Draft, draft: Draft, base: ProposalInputs, p: ScenarioParams) -> list[dict[str, Any]]:
    """For every variant whose supplier or quantity moved: what moved and which of the scenario's changes can account for it."""
    before = {ln.variant_id: ln for ln in base_draft.lines}
    after = {ln.variant_id: ln for ln in draft.lines}
    out = []
    for vid in sorted(set(before) | set(after)):
        a, b = before.get(vid), after.get(vid)
        if a is not None and b is not None and a.supplier_id == b.supplier_id and a.qty == b.qty:
            continue
        reasons: list[str] = []
        sup = {x.supplier_id for x in (a, b) if x is not None}
        if a is not None and a.supplier_id in p.disabled_suppliers:
            reasons.append("supplier_disabled")
        for sid in sorted(sup):
            d = p.supplier_deltas.get(sid)
            if d is not None:
                reasons += [f"{name}_changed" for name in DELTA_FIELDS if getattr(d, name) is not None]
        if p.service_level_delta != 0:
            reasons.append("service_level_changed")
        if p.budget is not None and (draft.over_budget != base_draft.over_budget or draft.optimized_total != base_draft.optimized_total):
            reasons.append("budget_changed")
        out.append({"variant_id": vid, "supplier_before": None if a is None else a.supplier_id, "supplier_after": None if b is None else b.supplier_id,
                    "qty_before": 0 if a is None else a.qty, "qty_after": 0 if b is None else b.qty, "reasons": list(dict.fromkeys(reasons)) or ["rebalanced_by_total_cost"]})
    return out


def binding_constraints(draft: Draft, p: ScenarioParams) -> list[dict[str, Any]]:
    """The constraints that shaped the result, strongest first: an exceeded budget, minimums that needed topping up or are not met, free-delivery thresholds reached."""
    out: list[dict[str, Any]] = []
    if draft.over_budget > 0:
        out.append({"key": "budget", "params": {"over_by": str(draft.over_budget)}})
    for g in draft.groups:
        if g.minimum_status == "shortfall":
            out.append({"key": f"min_order:{g.supplier_id}", "params": {"supplier_id": g.supplier_id, "status": "shortfall"}})
    for g in draft.groups:
        if g.minimum_status == "topped_up":
            out.append({"key": f"min_order:{g.supplier_id}", "params": {"supplier_id": g.supplier_id, "status": "topped_up"}})
    for g in draft.groups:
        if g.free_delivery:
            out.append({"key": f"free_delivery:{g.supplier_id}", "params": {"supplier_id": g.supplier_id}})
    if p.budget is not None and draft.over_budget == 0 and not any(c["key"] == "budget" for c in out) and draft.optimized_total >= p.budget * Decimal("0.95"):
        out.append({"key": "budget", "params": {"over_by": "0"}})            # within 5 % of the cap: it is shaping the result
    return out


def sensitivity(base: ProposalInputs, p: ScenarioParams, draft: Draft, top: int = SENSITIVITY_TOP) -> list[dict[str, Any]]:
    """Re-solves with each of the strongest binding constraints relaxed by 10 %; the cost impact is the change in total cost. Bounded: at most ``top`` solves."""
    out: list[dict[str, Any]] = []
    for c in binding_constraints(draft, p)[:top]:
        key = c["key"]
        trial = p
        if key == "budget":
            cur = p.budget if p.budget is not None else base.budget
            if cur is None:
                continue
            trial = replace(p, budget=(cur * (1 + SENSITIVITY_STEP)).quantize(Decimal("0.01")))
        else:
            kind, sid = key.split(":", 1)
            terms = base.suppliers.get(sid)
            d = p.supplier_deltas.get(sid, SupplierDelta())
            if kind == "min_order":
                cur = d.min_order_value if d.min_order_value is not None else (terms.min_order_value if terms else None)
                if cur is None:
                    continue
                trial = replace(p, supplier_deltas={**p.supplier_deltas, sid: replace(d, min_order_value=(cur * (1 - SENSITIVITY_STEP)).quantize(Decimal("0.01")))})
            else:
                cur = d.free_delivery_threshold if d.free_delivery_threshold is not None else (terms.free_delivery_threshold if terms else None)
                if cur is None:
                    continue
                trial = replace(p, supplier_deltas={**p.supplier_deltas, sid: replace(d, free_delivery_threshold=(cur * (1 - SENSITIVITY_STEP)).quantize(Decimal("0.01")))})
        alt = solve(apply_params(base, trial), SENSITIVITY_SECONDS)
        out.append({"constraint_key": key, "delta": "+10%" if key == "budget" else "-10%", "cost_impact": alt.optimized_total - draft.optimized_total})
    return out
