"""T032: the integration gate passes only when every plan step is integrated, or dropped with a reason."""

from __future__ import annotations

from gates import integration_gate as g


def step(pr, state, **kw):
    return {"pr": pr, "agent": "agent-01", "owned_paths": ["a/**"], "depends_on": [], "verification": ["contracts"], "state": state, **kw}


def plan(*steps):
    return {"base": "main", "steps": list(steps)}


def test_all_integrated_or_reentered_passes():
    assert g.run(plan(step(1, "integrated"), step(2, "fixed_reentered"))).result == "pass"


def test_dropped_with_reason_passes_but_without_reason_fails():
    assert g.run(plan(step(1, "dropped", drop_reason="gate_failed: cost"))).result == "pass"
    r = g.run(plan(step(1, "dropped")))
    assert r.result == "fail" and "pr 1" in r.evidence[0]
    assert g.run(plan(step(1, "dropped", drop_reason="  "))).result == "fail"


def test_pending_step_fails():
    assert g.run(plan(step(1, "integrated"), step(2, "pending"))).result == "fail"


def test_missing_or_empty_plan_is_not_run():
    assert g.run(None).result == "not_run"
    assert g.run(plan()).result == "not_run"
