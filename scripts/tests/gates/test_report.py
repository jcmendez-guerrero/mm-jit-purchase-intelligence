"""T006: aggregation, exit codes (0/1/2), six required gates and durations."""

from __future__ import annotations

import json

import jsonschema
from conftest import REPO
from gates import report as r


def _all(result: str) -> list[r.GateResult]:
    return [r.GateResult(g, result) for g in r.GATES]


def test_all_pass_is_zero():
    rep = r.build_report(_all("pass"))
    assert rep["overall"] == "pass" and r.exit_code(rep) == 0


def test_any_fail_is_one_even_with_not_run():
    results = _all("pass")
    results[0] = r.GateResult("contracts", "fail", ["x"])
    results[1] = r.GateResult("isolation", "not_run")
    assert r.exit_code(r.build_report(results)) == 1


def test_missing_gate_counts_as_not_run_and_is_filled_in():
    rep = r.build_report(_all("pass")[:5])
    assert rep["overall"] == "not_run" and r.exit_code(rep) == 2
    assert [g["gate"] for g in rep["gates"]] == list(r.GATES)


def test_report_matches_schema_and_has_durations():
    schema = json.loads((REPO / "docs/architecture/integration/schemas/gate-report.schema.json").read_text())
    rep = r.build_report(_all("pass"), [{"pr": 3, "agent": "agent-01", "reason": "gate_failed", "failed_gate": "cost"}])
    jsonschema.validate(rep, schema)
    assert all(r.seconds(g) >= 0 for g in rep["gates"])


def test_unknown_gate_or_result_rejected():
    for args in (("speed", "pass"), ("cost", "maybe")):
        try:
            r.GateResult(*args)
        except ValueError:
            continue
        raise AssertionError(args)
