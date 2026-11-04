"""T094: options for a supplier whose combined order is below its minimum, each with its cost impact.

* top_up:     add needed-soon items (cheapest cover first) until the minimum is met.
* reallocate: move the supplier's lines to the next-best supplier that offers them.
* accept:     keep the order below the minimum and flag it; the cost impact is the delivery risk, shown as zero cost.
Impacts are differences in total ticks (positive = costs more) against the plan as allocated.
"""

from __future__ import annotations

from dataclasses import dataclass

from proposals.model import ProposalInputs, SupplierTermsIn, ticks

from allocation.common import Allocation, Cand, Chosen, LineSpec, summarise


@dataclass(frozen=True)
class ShortfallOption:
    supplier_id: str
    kind: str                       # top_up / reallocate / accept
    cost_delta_ticks: int
    detail: dict[str, object]


def _met(group_sub: int, group_qty: int, t: SupplierTermsIn) -> bool:
    return ((t.min_order_value is None or group_sub >= ticks(t.min_order_value))
            and (not t.min_qty_for_delivery or group_qty >= t.min_qty_for_delivery))


def options_for(inputs: ProposalInputs, lines: list[LineSpec], alloc: Allocation) -> list[ShortfallOption]:
    out: list[ShortfallOption] = []
    by_line = {ln.variant_id: ln for ln in lines}
    ordered = {c.variant_id for c in alloc.chosen}
    base_total = alloc.total_ticks
    for g in alloc.groups:
        if g.minimum_status == "met":
            continue
        t = inputs.suppliers.get(g.supplier_id, SupplierTermsIn(g.supplier_id))
        # --- top up with needed-soon items this supplier offers
        pool: list[Cand] = []
        for ln in lines:
            if ln.variant_id in ordered:
                continue
            pool += [c for c in ln.cands if c.supplier_id == g.supplier_id and not ln.mandatory]
        sub, qty, added = g.subtotal_ticks, g.qty, []
        for c in sorted(pool, key=lambda c: (c.line_ticks, c.variant_id)):
            if _met(sub, qty, t):
                break
            sub, qty = sub + c.line_ticks, qty + c.qty
            added.append(c)
        if added and _met(sub, qty, t):
            extra = [Chosen(c.variant_id, c.supplier_id, c.qty, c.unit_ticks, c.line_ticks, c.lead, True) for c in added]
            new_total = sum(x.total_ticks for x in summarise(alloc.chosen + extra, inputs.suppliers))
            out.append(ShortfallOption(g.supplier_id, "top_up", new_total - base_total, {"variants": [c.variant_id for c in added]}))
        # --- move this supplier's lines elsewhere
        moved: list[Chosen] = []
        feasible = True
        for c in [c for c in alloc.chosen if c.supplier_id == g.supplier_id and not c.topup]:   # top-up lines simply drop out
            alts = [x for x in by_line[c.variant_id].cands if x.supplier_id != g.supplier_id] if c.variant_id in by_line else []
            if not alts:
                feasible = False
                break
            best = min(alts, key=lambda x: (x.line_ticks + x.risk_ticks, x.lead, x.supplier_id))
            moved.append(Chosen(best.variant_id, best.supplier_id, best.qty, best.unit_ticks, best.line_ticks, best.lead, c.topup))
        if feasible and moved:
            rest = [c for c in alloc.chosen if c.supplier_id != g.supplier_id]   # includes dropping this supplier's top-ups
            new_total = sum(x.total_ticks for x in summarise(rest + moved, inputs.suppliers))
            out.append(ShortfallOption(g.supplier_id, "reallocate", new_total - base_total,
                                       {"to": sorted({m.supplier_id for m in moved}), "variants": [m.variant_id for m in moved]}))
        out.append(ShortfallOption(g.supplier_id, "accept", 0, {"shortfall_value_ticks": g.shortfall_value_ticks, "shortfall_qty": g.shortfall_qty}))
    return out

