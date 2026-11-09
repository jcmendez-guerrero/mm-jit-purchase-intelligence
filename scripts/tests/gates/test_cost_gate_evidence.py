"""T057: when the cost guardrails fail, the failure line names the Bicep file and the resource or setting (FR-015)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from conftest import REPO
from gates import suite_gate


def _run_with(tmp_path: Path, filename: str, text: str) -> str:
    """Run the cost gate's pytest command on a copy of the Bicep tree that also holds one bad module; return the evidence."""
    shutil.copytree(REPO / "infra/bicep", tmp_path / "infra/bicep")
    (tmp_path / "infra/tests").mkdir(parents=True)
    shutil.copy(REPO / "infra/tests/test_cost_guardrails.py", tmp_path / "infra/tests/")
    (tmp_path / "infra/bicep/modules" / filename).write_text(text, encoding="utf-8")
    cmd = suite_gate.Cmd((sys.executable, "-m", "pytest", "-q", "-rf", "infra/tests/test_cost_guardrails.py"))
    result = suite_gate.run_commands("cost", [cmd], tmp_path)
    assert result.result == "fail"
    return "\n".join(result.evidence)


def failed_lines(evidence: str) -> str:
    return evidence


def test_a_forbidden_resource_is_reported_with_its_file_and_type(tmp_path):
    out = failed_lines(_run_with(tmp_path, "bad.bicep", "resource r 'Microsoft.Cache/redis@2023-08-01' = {\n}\n"))
    assert "bad.bicep" in out and "Microsoft.Cache/redis" in out


def test_a_parallel_job_is_reported_with_its_file(tmp_path):
    out = failed_lines(_run_with(tmp_path, "bad.bicep", "var x = {\n  parallelism: 3\n}\n"))
    assert "bad.bicep" in out and "parallelism" in out


def test_the_gate_evidence_keeps_those_failed_lines():
    cmd = suite_gate.Cmd(("pytest",))
    line = "FAILED infra/tests/test_cost_guardrails.py::test_x - AssertionError: bad.bicep declares Microsoft.Cache/redis"
    assert "bad.bicep declares Microsoft.Cache/redis" in suite_gate._evidence(cmd, 1, f"...\n{line}\n1 failed\n")
