"""T092: greedy baseline. Each line takes its cheapest eligible offer; minimums are checked afterwards and flagged.

Used as the comparator in explanations, as the solver-timeout fallback and as the reference the optimiser must beat.
"""

from __future__ import annotations

from proposals.model import ProposalInputs

from allocation.common import Allocation, Cand, Chosen, LineSpec, budget_excess, summarise


def pick(line: LineSpec) -> Cand | None:
    cands = [c for c in line.cands if line.fixed_supplier is None or c.supplier_id == line.fixed_supplier] or list(line.cands)
    return min(cands, key=lambda c: (c.line_ticks + c.risk_ticks, c.lead, c.supplier_id), default=None)


def allocate_greedy(inputs: ProposalInputs, lines: list[LineSpec]) -> Allocation:
    chosen: list[Chosen] = []
    notes: list[str] = []
    for line in lines:
        if not line.mandatory:
            continue
        c = pick(line)
        if c is None:
            notes.append(f"no_eligible_supplier:{line.variant_id}")
            continue
        chosen.append(Chosen(c.variant_id, c.supplier_id, c.qty, c.unit_ticks, c.line_ticks, c.lead, False))
    groups = summarise(chosen, inputs.suppliers)
    return Allocation(chosen, groups, "greedy", sum(g.total_ticks for g in groups), budget_excess(groups, inputs.budget), notes)
