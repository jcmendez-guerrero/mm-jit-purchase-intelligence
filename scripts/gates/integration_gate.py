"""Integration gate (T033, spec FR-009): every plan step is integrated, or dropped with a recorded reason."""

from __future__ import annotations

from .report import GateResult, utc_now

OK = {"integrated", "fixed_reentered"}


def run(plan: dict | None) -> GateResult:
    started = utc_now()
    if not plan or not plan.get("steps"):
        return GateResult("integration", "not_run", ["no PRs in the integration plan yet (the maintainer supplies the list)"], started)
    problems = []
    for s in plan["steps"]:
        if s["state"] in OK:
            continue
        if s["state"] == "dropped" and str(s.get("drop_reason", "")).strip():
            continue
        problems.append(f"pr {s['pr']} ({s['agent']}) is {s['state']}" + ("" if s["state"] != "dropped" else " without a recorded reason"))
    return GateResult("integration", "fail" if problems else "pass", problems or [f"{len(plan['steps'])} steps accounted for"], started)
