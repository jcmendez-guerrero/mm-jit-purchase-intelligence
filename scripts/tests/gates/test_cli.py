"""T069: the command-line layer: exit codes, report files, summary output and `integrate` end to end (stub gates)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest
from conftest import REPO, git, write_json
from gates import __main__ as cli
from gates import integrate as ig
from gates import report as r
from gates.report import GateResult


def stub_runner(failing: str | None = None, bad_file: str | None = None):
    """make_runner replacement: every gate passes, except `failing`, or `contracts` when `bad_file` exists in the tree."""
    def make_runner(plan, openapi=None):
        def run_gates(root: Path, gates):
            out = []
            for g in gates:
                broken = g == failing or (bad_file and g == "contracts" and any(root.rglob(bad_file)))
                out.append(GateResult(g, "fail" if broken else "pass", ["stub"]))
            return out
        return run_gates
    return make_runner


@pytest.fixture
def patched(monkeypatch, valid_artifacts):
    monkeypatch.setattr(cli, "ROOT", valid_artifacts)
    return valid_artifacts


def test_validate_exit_codes(patched):
    assert cli.main(["validate"]) == 0
    (patched / "docs/architecture/integration/integration-plan.json").unlink()
    assert cli.main(["validate"]) == 3


def test_run_writes_a_valid_report_and_maps_results_to_exit_codes(patched, monkeypatch, tmp_path):
    schema = json.loads((REPO / "docs/architecture/integration/schemas/gate-report.schema.json").read_text())
    out = tmp_path / "report.json"
    monkeypatch.setattr(cli, "make_runner", stub_runner())
    assert cli.main(["run", "--report", str(out)]) == 0
    jsonschema.validate(json.loads(out.read_text()), schema)
    monkeypatch.setattr(cli, "make_runner", stub_runner(failing="cost"))
    assert cli.main(["run", "--report", str(out)]) == 1
    monkeypatch.setattr(cli, "make_runner", stub_runner())
    assert cli.main(["run", "--gate", "cost", "--report", str(out)]) == 0  # only the requested gate counts
    assert json.loads(out.read_text())["overall"] == "pass"
    monkeypatch.setattr(cli, "make_runner", stub_runner(failing="cost"))
    assert cli.main(["run", "--gate", "cost", "--report", str(out)]) == 1
    monkeypatch.setattr(cli, "make_runner", stub_runner())
    assert cli.main(["run", "--gate", "contracts", "--gate", "isolation", "--report", str(out)]) == 0  # what the CI gates job runs


def test_summary_prints_markdown_for_a_pr(tmp_path, capsys):
    dropped = [{"pr": 7, "agent": "agent-01", "reason": "gate_failed", "failed_gate": "cost"}]
    path = tmp_path / "report.json"
    write_json(path, r.build_report([GateResult(g, "pass", ["ok"]) for g in r.GATES], dropped))
    assert cli.main(["summary", "--report", str(path), "--pr", "7"]) == 0
    assert "PR 7 was dropped" in capsys.readouterr().out


def test_markdown_renderers_write_their_files(patched):
    assert cli.main(["audit-md"]) == 0 and cli.main(["matrix-md"]) == 0
    base = patched / "docs/architecture/integration"
    assert (base / "feature-status.md").read_text().startswith("# Feature status")
    assert (base / "contract-matrix.md").read_text().startswith("# Contract matrix")


def test_lookup_prints_owner_version_consumers_and_status_and_exits_3_for_an_unknown_name(patched, capsys):
    assert cli.main(["lookup", "money"]) == 0
    out = capsys.readouterr().out
    assert "money" in out and "v1" in out and "svc" in out and "frozen" in out
    assert cli.main(["lookup", "does-not-exist"]) == 3
    assert "does-not-exist" in capsys.readouterr().err
    (patched / "docs/architecture/integration/contract-matrix.json").unlink()
    assert cli.main(["lookup", "money"]) == 3  # no matrix at all is an error, not an empty answer


def test_integrate_with_an_invalid_plan_exits_3_with_a_clear_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    plan = tmp_path / "plan.json"
    step = {"pr": 1, "agent": "agent-01", "owned_paths": ["a/**"], "depends_on": [9], "verification": ["contracts"], "state": "pending"}
    write_json(plan, {"base": "main", "steps": [step]})
    assert cli.main(["integrate", "--plan", str(plan)]) == 3
    assert "unknown pr 9" in capsys.readouterr().err


def _repo(path: Path) -> Path:
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "t@example.test")
    git(path, "config", "user.name", "t")
    (path / "a").mkdir()
    (path / "a/base.txt").write_text("base\n")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "base")
    for name, files in (("pr1", {"a/one.txt": "1"}), ("pr2", {"a/BAD": "x"})):
        git(path, "checkout", "-q", "-b", name, "main")
        for rel, text in files.items():
            (path / rel).write_text(text)
        git(path, "add", ".")
        git(path, "commit", "-q", "-m", name)
        git(path, "checkout", "-q", "main")
    return path


def test_integrate_end_to_end_with_prepare_steps_and_the_recomputed_integration_gate(tmp_path, monkeypatch):
    repo = _repo(tmp_path / "repo")
    marker = tmp_path / "markers"
    marker.mkdir()

    def touch(name):  # a harmless stand-in for `uv pip install` / `npm ci`: it only leaves a marker file
        return [sys.executable, "-c", f"open({str(marker / name)!r}, 'w').write('x')"]

    monkeypatch.setattr(ig, "install_command", lambda tree: touch("install"))
    monkeypatch.setattr(ig, "web_commands", lambda tree: [(touch("web"), tree)])
    monkeypatch.setattr(cli, "ROOT", repo)
    monkeypatch.setattr(cli, "make_runner", stub_runner(bad_file="BAD"))
    # the command resolves PR heads as refs/pull/N/head; point those at the throwaway branches
    for n in (1, 2):
        git(repo, "update-ref", f"refs/pull/{n}/head", f"pr{n}")
    steps = [{"pr": n, "agent": "agent-01", "owned_paths": ["a/**"], "depends_on": [], "verification": ["contracts"], "state": "pending"}
             for n in (1, 2)]
    plan = tmp_path / "plan.json"
    write_json(plan, {"base": "main", "steps": steps})
    out = tmp_path / "report.json"
    main_before = git(repo, "rev-parse", "main")

    code = cli.main(["integrate", "--plan", str(plan), "--install", "--web", "--report", str(out)])

    report = json.loads(out.read_text())
    assert {p.name for p in marker.iterdir()} == {"install", "web"}
    assert report["integrated"] == [1] and [d["pr"] for d in report["dropped_prs"]] == [2]
    integration = next(g for g in report["gates"] if g["gate"] == "integration")
    assert integration["result"] == "pass"  # every step is integrated, or dropped with a recorded reason
    assert code == 0 and report["overall"] == "pass"
    assert git(repo, "rev-parse", "main") == main_before
