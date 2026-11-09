"""T004/T029: artifact validation, schema-copy equality and integration-plan semantics."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import SCHEMAS, write_json
from gates import validate as v


def test_valid_artifacts_pass(valid_artifacts: Path):
    assert v.validate(valid_artifacts) == []


def test_missing_artifact_is_reported(root: Path):
    assert any("feature-status.json: missing" in e for e in v.validate(root))


def test_schema_violation_is_reported(valid_artifacts: Path):
    path = valid_artifacts / "docs/architecture/integration/feature-status.json"
    data = json.loads(path.read_text())
    data["features"][0]["status"] = "done"
    write_json(path, data)
    assert any("feature-status.json" in e for e in v.validate(valid_artifacts))


def test_complete_requires_known_status_and_evidence_shape(valid_artifacts: Path):
    path = valid_artifacts / "docs/architecture/integration/feature-status.json"
    data = json.loads(path.read_text())
    data["features"][0]["evidence"] = ["no-line-number"]
    write_json(path, data)
    assert v.validate(valid_artifacts)


def test_schema_copy_drift_fails(valid_artifacts: Path):
    copy = valid_artifacts / SCHEMAS / "gate-report.schema.json"
    data = json.loads(copy.read_text())
    data["title"] = "Changed"
    write_json(copy, data)
    assert any("differs" in e for e in v.validate(valid_artifacts))


def _plan(steps):
    return {"base": "main", "steps": steps}


def _step(pr, deps=(), paths=("a/**",)):
    return {"pr": pr, "agent": "agent-01", "owned_paths": list(paths), "depends_on": list(deps),
            "verification": ["contracts"], "state": "pending"}


def test_plan_missing_owned_paths_is_rejected(valid_artifacts: Path):
    write_json(valid_artifacts / "docs/architecture/integration/integration-plan.json", _plan([_step(1, paths=())]))
    assert v.validate(valid_artifacts)


def test_plan_unknown_gate_is_rejected(valid_artifacts: Path):
    step = _step(1)
    step["verification"] = ["speed"]
    write_json(valid_artifacts / "docs/architecture/integration/integration-plan.json", _plan([step]))
    assert v.validate(valid_artifacts)


def _owned(pr, agent, *paths):
    return {**_step(pr, paths=paths), "agent": agent}


def test_two_agents_may_not_claim_overlapping_paths():
    errors = v.plan_errors(_plan([_owned(1, "agent-01", "a/**"), _owned(2, "agent-02", "a/b/**")]))
    assert any("pr 1" in e and "pr 2" in e and "overlap" in e for e in errors)
    assert v.plan_errors(_plan([_owned(1, "agent-01", "a/**"), _owned(2, "agent-02", "b/**")])) == []
    assert v.plan_errors(_plan([_owned(1, "agent-01", "a/x.py"), _owned(2, "agent-02", "a/y.py")])) == []
    assert any("overlap" in e for e in v.plan_errors(_plan([_owned(1, "agent-01", "a/*.py"), _owned(2, "agent-02", "a/b/**")])))
    assert any("overlap" in e for e in v.plan_errors(_plan([_owned(1, "agent-01", "**"), _owned(2, "agent-02", "b/x.py")])))


def test_the_same_agent_may_overlap_itself():
    assert v.plan_errors(_plan([_owned(1, "agent-01", "a/**"), _owned(2, "agent-01", "a/b/**")])) == []


def test_an_error_in_one_artifact_does_not_hide_checks_on_the_others(valid_artifacts: Path):
    copy = valid_artifacts / SCHEMAS / "gate-report.schema.json"
    data = json.loads(copy.read_text())
    data["title"] = "Changed"
    write_json(copy, data)  # a drifted schema copy
    write_json(valid_artifacts / "docs/architecture/integration/integration-plan.json", _plan([_step(1, [2]), _step(2, [1])]))
    errors = v.validate(valid_artifacts)
    assert any("differs" in e for e in errors) and any("dependency cycle" in e for e in errors)


def test_plan_cycle_and_unknown_dependency():
    assert "dependency cycle in steps" in v.plan_errors(_plan([_step(1, [2]), _step(2, [1])]))
    assert any("unknown pr" in e for e in v.plan_errors(_plan([_step(1, [9])])))
    assert v.plan_errors(_plan([_step(1), _step(2, [1])])) == []
