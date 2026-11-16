"""T093: OR-Tools CP-SAT allocation over integer ticks (1/10000 EUR) and whole units.

One supplier per line (binary choice). Supplier fixed-charge variables model the delivery charge, the free-delivery
threshold, the minimum order value and the minimum quantity for delivery. Needed-soon items are optional top-up lines
that the solver adds only when that lowers the total (e.g. to reach a minimum or a free-delivery threshold). Minimums
and the budget are soft with a large penalty, so an unreachable minimum yields a flagged shortfall instead of
infeasibility. Deterministic (one worker, fixed seed) and time-boxed; a timeout without a solution falls back to the
greedy plan.
"""

from __future__ import annotations

from ortools.sat.python import cp_model
from proposals.model import ProposalInputs, SupplierTermsIn, ticks

from allocation.common import (
    Allocation,
    Chosen,
    LineSpec,
    budget_excess,
    percent_basis_points,
    summarise,
    threshold_units,
)
from allocation.greedy import allocate_greedy

BIG = 1_000_000       # penalty per tick of violated minimum / budget: dwarfs any real saving, and stays far inside int64
MAX_TICKS = 10**10    # 1,000,000 EUR: upper bound for money variables
DEFER_STEP = 10       # ticks: how much more it costs to defer a more urgent line (order of deferral only; never enough to defer without a cap)


def _discount_expr(m: cp_model.CpModel, t: SupplierTermsIn, sid: str, y: cp_model.IntVar, subtotal: cp_model.IntVar, qty: object) -> cp_model.IntVar | None:
    """The best qualifying discount tier of an order (the solver may use at most one, and minimising cost makes it the best).
    Thresholds are judged on the list subtotal / units, before the discount - the same rule as ``summarise``."""
    if not t.discounts:
        return None
    uses, applied_vars = [], []
    for k, d in enumerate(t.discounts):
        measure = subtotal if d.basis == "order_value" else qty
        threshold = ticks(d.threshold) if d.basis == "order_value" else threshold_units(d)
        met = m.NewBoolVar(f"dmet_{sid}_{k}")
        m.Add(measure >= threshold).OnlyEnforceIf(met)  # type: ignore[operator]
        m.Add(measure < threshold).OnlyEnforceIf(met.Not())  # type: ignore[operator]
        use = m.NewBoolVar(f"duse_{sid}_{k}")
        m.Add(use <= met)
        m.Add(use <= y)
        raw = m.NewIntVar(0, MAX_TICKS, f"draw_{sid}_{k}")
        if d.kind == "percent":
            num = m.NewIntVar(0, MAX_TICKS * 10_000, f"dnum_{sid}_{k}")
            m.Add(num == subtotal * percent_basis_points(d.value))
            m.AddDivisionEquality(raw, num, 10_000)
        else:
            m.AddMinEquality(raw, [ticks(d.value), subtotal])
        applied = m.NewIntVar(0, MAX_TICKS, f"dapp_{sid}_{k}")
        m.Add(applied == raw).OnlyEnforceIf(use)
        m.Add(applied == 0).OnlyEnforceIf(use.Not())
        uses.append(use)
        applied_vars.append(applied)
    m.Add(sum(uses) <= 1)
    total = m.NewIntVar(0, MAX_TICKS, f"discount_{sid}")
    m.Add(total == sum(applied_vars))
    return total


def allocate_cpsat(inputs: ProposalInputs, lines: list[LineSpec], time_limit_s: float = 30.0, seed: int = 1) -> Allocation:
    lines = [ln for ln in lines if ln.cands]
    m = cp_model.CpModel()
    sel: dict[tuple[int, str], cp_model.IntVar] = {}
    by_supplier: dict[str, list[tuple[object, cp_model.IntVar]]] = {}
    cost_terms: list[object] = []
    penalties: list[object] = []
    defer_vars: dict[int, cp_model.IntVar] = {}
    capped = inputs.defer_for_cap and (inputs.budget is not None or bool(inputs.supplier_budgets))
    for ln in lines:
        vars_for_line = []
        for c in ln.cands:
            b = m.NewBoolVar(f"b_{c.variant_id}_{c.supplier_id}")
            sel[(c.variant_id, c.supplier_id)] = b
            vars_for_line.append(b)
            by_supplier.setdefault(c.supplier_id, []).append((c, b))
            cost_terms.append((c.line_ticks + c.risk_ticks) * b)
            if ln.fixed_supplier is not None and c.supplier_id != ln.fixed_supplier and any(x.supplier_id == ln.fixed_supplier for x in ln.cands):
                m.Add(b == 0)
        if ln.mandatory and capped and not ln.critical and ln.fixed_supplier is None and ln.fixed_qty is None:
            # A needed line may be deferred only when a cap forces it: leaving it out costs more than the line itself, so without budget
            # pressure it is always bought, and under pressure the least urgent lines (urgency 1) go first. Critical and buyer-fixed lines never do.
            d = m.NewBoolVar(f"defer_{ln.variant_id}")
            defer_vars[ln.variant_id] = d
            m.Add(sum(vars_for_line) + d == 1)
            penalties.append((max(c.line_ticks + c.risk_ticks for c in ln.cands) + DEFER_STEP * ln.urgency) * d)
        elif ln.mandatory:
            m.Add(sum(vars_for_line) == 1)
        else:
            m.Add(sum(vars_for_line) <= 1)
    total_terms: list[object] = []
    y_by_supplier: dict[str, cp_model.IntVar] = {}
    for sid, items in sorted(by_supplier.items()):
        t: SupplierTermsIn = inputs.suppliers.get(sid, SupplierTermsIn(sid))
        y = m.NewBoolVar(f"y_{sid}")
        y_by_supplier[sid] = y
        for _, b in items:
            m.Add(b <= y)
        m.Add(sum(b for _, b in items) >= y)
        sub = sum(c.line_ticks * b for c, b in items)  # type: ignore[attr-defined]
        qty = sum(c.qty * b for c, b in items)  # type: ignore[attr-defined]
        subtotal = m.NewIntVar(0, MAX_TICKS, f"sub_{sid}")
        m.Add(subtotal == sub)
        if t.min_order_value is not None:
            short = m.NewIntVar(0, ticks(t.min_order_value), f"shortv_{sid}")
            m.Add(short >= ticks(t.min_order_value) * y - subtotal)
            penalties.append(BIG * short)
        if t.min_qty_for_delivery:
            shortq = m.NewIntVar(0, t.min_qty_for_delivery, f"shortq_{sid}")
            m.Add(shortq >= t.min_qty_for_delivery * y - qty)
            penalties.append(BIG * shortq)
        charge = ticks(t.delivery_charge) if t.delivery_charge is not None else 0
        if t.free_delivery_threshold is not None and charge:
            z = m.NewBoolVar(f"free_{sid}")
            m.Add(subtotal >= ticks(t.free_delivery_threshold)).OnlyEnforceIf(z)
            m.Add(subtotal < ticks(t.free_delivery_threshold)).OnlyEnforceIf(z.Not())
            m.Add(z <= y)
            paid = m.NewBoolVar(f"paid_{sid}")
            m.Add(paid == y - z)
            charge_expr = charge * paid
        elif charge:
            charge_expr = charge * y
        else:
            charge_expr = None
        total_terms.append(subtotal)
        discount = _discount_expr(m, t, sid, y, subtotal, qty)
        if discount is not None:
            cost_terms.append(-discount)
            total_terms.append(-discount)
        if charge_expr is not None:
            cost_terms.append(charge_expr)
            total_terms.append(charge_expr)
        cap = inputs.supplier_budgets.get(sid)
        if cap is not None:                                  # this supplier's own weekly cap: soft like the global one, so a critical line can still be bought
            over_s = m.NewIntVar(0, MAX_TICKS, f"over_{sid}")
            own = [subtotal] + ([-discount] if discount is not None else []) + ([charge_expr] if charge_expr is not None else [])
            m.Add(over_s >= sum(own) - ticks(cap))
            penalties.append(BIG * over_s)
    if inputs.budget is not None:
        over = m.NewIntVar(0, MAX_TICKS, "over_budget")
        m.Add(over >= sum(total_terms) - ticks(inputs.budget))
        penalties.append(BIG * over)
    m.Minimize(sum(cost_terms) + sum(penalties))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = seed
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        fallback = allocate_greedy(inputs, lines)
        fallback.solver_status = "fallback_greedy"
        fallback.notes.append("solver_no_solution")
        return fallback
    chosen: list[Chosen] = []
    for ln in lines:
        for c in ln.cands:
            if solver.Value(sel[(c.variant_id, c.supplier_id)]):
                chosen.append(Chosen(c.variant_id, c.supplier_id, c.qty, c.unit_ticks, c.line_ticks, c.lead, not ln.mandatory))
    groups = summarise(chosen, inputs.suppliers)
    deferred = sorted(vid for vid, d in defer_vars.items() if solver.Value(d))
    supplier_over = {g.supplier_id: g.total_ticks - ticks(inputs.supplier_budgets[g.supplier_id]) for g in groups
                     if g.supplier_id in inputs.supplier_budgets and g.total_ticks > ticks(inputs.supplier_budgets[g.supplier_id])}
    return Allocation(chosen, groups, "optimal" if status == cp_model.OPTIMAL else "feasible", sum(g.total_ticks for g in groups), budget_excess(groups, inputs.budget),
                      deferred=deferred, supplier_over=supplier_over)
