"""T143: scenario persistence and the create / promote / export flows. A scenario never writes proposals, terms, policies or anything ERP-related
unless it is explicitly promoted, and promotion goes through the normal proposal path (a draft that someone else has to approve)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from audit.chain import append as audit
from db.tables import product_refs, proposals, scenario_results, scenario_sensitivity, scenarios, suppliers
from mmi_common.time import get_correlation_id, set_correlation_id
from proposals.export import export_csv, export_xlsx
from proposals.generate import RULE_VERSIONS, Draft, store
from proposals.model import ProposalInputs
from proposals.publisher import BlobWriter, scenario_ready
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Row

from scenarios.engine import (
    ScenarioError,
    ScenarioParams,
    apply_params,
    binding_constraints,
    explain_changes,
    input_fingerprint,
    result_hash,
    sensitivity,
    solve,
)

Q2 = Decimal("0.01")


class ScenarioStateError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _get_row(conn: Connection, sid: str) -> Row[Any]:
    r = conn.execute(select(scenarios).where(scenarios.c.id == sid)).first()
    if r is None:
        raise ScenarioStateError("unknown_scenario")
    return r


def _critical(draft: Draft) -> list[int]:
    return sorted(ln.variant_id for ln in draft.lines if ln.explanation.get("clinical_critical") and ln.qty > 0)


def create(conn: Connection, writer: BlobWriter, name: str, params: ScenarioParams, base: ProposalInputs, actor: str, idempotency_key: str, now: datetime | None = None,
           time_limit_s: float = 20.0) -> dict[str, Any]:
    """Solves the baseline and the scenario, stores the comparison and returns it. Repeating the same Idempotency-Key returns the stored scenario."""
    now = now or datetime.now(UTC)
    name = (name or "").strip()
    if not name or len(name) > 200:
        raise ScenarioError("a name is required")
    params.validate()
    existing = conn.execute(select(scenarios.c.id).where(scenarios.c.idempotency_key == idempotency_key)).first()
    if existing is not None:
        return get(conn, existing.id)
    sid = str(uuid.uuid4())
    versions = {"inputs_fingerprint": input_fingerprint(base), "rules": RULE_VERSIONS, "terms": base.terms_versions, "policy": base.policy_versions}
    conn.execute(insert(scenarios).values(id=sid, name=name, parameters=params.to_json(), status="computing", input_versions=versions, idempotency_key=idempotency_key,
                                          created_by=actor, created_at=now))
    try:
        baseline = solve(base, time_limit_s)
        draft = solve(apply_params(base, params), time_limit_s)
        _persist(conn, sid, params, base, baseline, draft)
        status = "ready"
    except Exception:
        conn.execute(update(scenarios).where(scenarios.c.id == sid).values(status="failed"))
        status = "failed"
    audit(conn, actor, "scenario.created", "scenario", sid, after={"name": name, "status": status, "parameters": params.to_json()}, now=now)
    scenario_ready(conn, writer, sid, status, get_correlation_id() or set_correlation_id())
    return get(conn, sid)


def _persist(conn: Connection, sid: str, params: ScenarioParams, base: ProposalInputs, baseline: Draft, draft: Draft) -> None:
    binding = binding_constraints(draft, params)
    for g in draft.groups:
        lines = [{"variant_id": ln.variant_id, "qty": ln.qty, "unit_cost": str(ln.unit_cost), "line_total": str(ln.line_total), "clinical_critical": bool(ln.explanation.get("clinical_critical"))}
                 for ln in draft.lines if ln.supplier_id == g.supplier_id]
        budget = params.budget if params.budget is not None else base.budget
        util = None if not budget else (g.total / budget).quantize(Decimal("0.0001"))
        conn.execute(insert(scenario_results).values(scenario_id=sid, supplier_id=g.supplier_id, lines=lines, order_total=g.total, expected_delivery=g.expected_delivery,
                                                     budget_utilisation=util, binding_constraints=[c for c in binding if c["key"].endswith(f":{g.supplier_id}")]))
    for s in sensitivity(base, params, draft):
        conn.execute(insert(scenario_sensitivity).values(scenario_id=sid, constraint_key=s["constraint_key"], delta=s["delta"], cost_impact=s["cost_impact"]))
    budget = params.budget if params.budget is not None else base.budget
    summary = {
        "baseline": {"total": str(baseline.optimized_total.quantize(Q2)), "over_budget": str(baseline.over_budget.quantize(Q2)), "lines": len(baseline.lines)},
        "scenario": {"total": str(draft.optimized_total.quantize(Q2)), "over_budget": str(draft.over_budget.quantize(Q2)), "lines": len(draft.lines), "budget": None if budget is None else str(budget),
                     "utilisation": None if not budget else str((draft.optimized_total / budget).quantize(Decimal("0.0001")))},
        "delta_total": str((draft.optimized_total - baseline.optimized_total).quantize(Q2)),
        "changes": explain_changes(baseline, draft, base, params), "binding": binding,
        "infeasible": None if draft.over_budget <= 0 else {"over_by": str(draft.over_budget.quantize(Q2)), "clinical_critical_variants": _critical(draft)},
        "notes": list(draft.notes),
    }
    conn.execute(update(scenarios).where(scenarios.c.id == sid).values(status="ready", result_hash=result_hash(draft), summary=summary))


def get(conn: Connection, sid: str) -> dict[str, Any]:
    s = _get_row(conn, sid)
    names = {r.id: r.name for r in conn.execute(select(suppliers.c.id, suppliers.c.name)).all()}
    results = [{"supplier_id": r.supplier_id, "supplier_name": names.get(r.supplier_id), "lines": r.lines, "order_total": str(Decimal(str(r.order_total)).quantize(Q2)),
                "expected_delivery": r.expected_delivery.isoformat() if r.expected_delivery else None,
                "budget_utilisation": None if r.budget_utilisation is None else str(r.budget_utilisation), "binding_constraints": r.binding_constraints or []}
               for r in conn.execute(select(scenario_results).where(scenario_results.c.scenario_id == sid).order_by(scenario_results.c.supplier_id)).all()]
    sens = [{"constraint_key": r.constraint_key, "delta": r.delta, "cost_impact": str(Decimal(str(r.cost_impact)).quantize(Q2))}
            for r in conn.execute(select(scenario_sensitivity).where(scenario_sensitivity.c.scenario_id == sid).order_by(scenario_sensitivity.c.id)).all()]
    return {"id": s.id, "name": s.name, "status": s.status, "parameters": s.parameters, "input_versions": s.input_versions, "result_hash": s.result_hash, "created_by": s.created_by,
            "created_at": s.created_at.isoformat(), "summary": s.summary, "results": results, "sensitivity": sens}


def listing(conn: Connection, limit: int = 50) -> list[dict[str, Any]]:
    return [{"id": r.id, "name": r.name, "status": r.status, "created_by": r.created_by, "created_at": r.created_at.isoformat(), "result_hash": r.result_hash,
             "delta_total": (r.summary or {}).get("delta_total")} for r in conn.execute(select(scenarios).order_by(scenarios.c.created_at.desc()).limit(min(limit, 200))).all()]


def promote(conn: Connection, sid: str, base: ProposalInputs, actor: str, week: str, now: datetime | None = None, time_limit_s: float = 20.0) -> dict[str, Any]:
    """Re-solves with today's inputs; if the result is not the stored one the scenario is stale and nothing is created. Otherwise a normal draft proposal
    is stored (created by the promoter, so a different approver with a fresh second factor must approve it)."""
    now = now or datetime.now(UTC)
    s = _get_row(conn, sid)
    if s.status == "promoted":
        raise ScenarioStateError("scenario_already_promoted")
    if s.status != "ready":
        raise ScenarioStateError("scenario_not_ready")
    params = ScenarioParams.from_json(s.parameters)
    draft = solve(apply_params(base, params), time_limit_s)
    if result_hash(draft) != s.result_hash:
        raise ScenarioStateError("scenario_stale")
    before = {r.id for r in conn.execute(select(proposals.c.id).where(proposals.c.week == week, proposals.c.status != "superseded")).all()}
    pid = store(conn, draft, actor, week, params.budget if params.budget is not None else base.budget, now)
    conn.execute(update(proposals).where(proposals.c.id == pid).values(scenario_id=sid))
    conn.execute(update(scenarios).where(scenarios.c.id == sid).values(status="promoted"))
    audit(conn, actor, "scenario.promoted", "scenario", sid, before={"status": "ready"}, after={"status": "promoted", "proposal_id": pid, "week": week}, now=now)
    return {"scenario_id": sid, "proposal_id": pid, "week": week, "superseded": sorted(before - {pid})}


def export_rows(conn: Connection, sid: str) -> list[list[Any]]:
    """Same columns as the proposal export, so the buyer reads both the same way."""
    s = get(conn, sid)
    ref = {r.variant_id: r for r in conn.execute(select(product_refs)).all()}
    out: list[list[Any]] = []
    for r in s["results"]:
        eta = date.fromisoformat(r["expected_delivery"]) if r["expected_delivery"] else None
        for ln in r["lines"]:
            if ln["qty"] <= 0:
                continue
            p = ref.get(ln["variant_id"])
            out.append([r["supplier_name"] or r["supplier_id"], (p.sku if p else None) or "", (p.name if p else None) or "", ln["variant_id"], ln["qty"],
                        Decimal(ln["unit_cost"]), Decimal(ln["line_total"]), eta])
    return out


def export(conn: Connection, sid: str, fmt: str) -> bytes:
    rows = export_rows(conn, sid)
    return export_csv(rows) if fmt == "csv" else export_xlsx(rows)



