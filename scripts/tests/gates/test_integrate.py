"""T022: integration branch building, ordering, dropping and isolation from main (throwaway git repos)."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import git
from gates import integrate as ig
from gates.report import GateResult


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@example.test")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a").mkdir()
    (tmp_path / "a/base.txt").write_text("base\n")
    (tmp_path / "b").mkdir()
    (tmp_path / "b/base.txt").write_text("base\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def branch(repo: Path, name: str, files: dict[str, str]) -> None:
    git(repo, "checkout", "-q", "-b", name, "main")
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", name)
    git(repo, "checkout", "-q", "main")


def step(pr, paths, deps=(), gates=("contracts",)):
    return {"pr": pr, "agent": f"agent-0{pr}", "owned_paths": paths, "depends_on": list(deps),
            "verification": list(gates), "state": "pending"}


def gates_stub(tree: Path, gates):
    """Fails the `contracts` gate when a file named BAD exists in the integrated tree."""
    bad = any(tree.rglob("BAD"))
    return [GateResult(g, "fail" if (bad and g == "contracts") else "pass", ["stub"]) for g in gates]


def run(repo, steps):
    return ig.integrate(repo, {"base": "main", "steps": steps}, gates_stub, ref_for=lambda pr: f"pr{pr}")


def dropped(report):
    return {d["pr"]: d["reason"] for d in report.get("dropped_prs", [])}


def test_integrates_in_dependency_order_and_leaves_main_alone(repo):
    branch(repo, "pr1", {"a/one.txt": "1"})
    branch(repo, "pr2", {"b/two.txt": "2"})
    main_before = git(repo, "rev-parse", "main")
    report = run(repo, [step(2, ["b/**"], [1]), step(1, ["a/**"])])  # listed out of order
    assert report["integrated"] == [1, 2] and "dropped_prs" not in report
    assert git(repo, "rev-parse", "main") == main_before
    assert "integration" not in git(repo, "branch", "--list")
    assert len(git(repo, "worktree", "list").splitlines()) == 1
    assert git(repo, "remote") == ""


def test_failing_gate_drops_pr_and_dependents_but_continues(repo):
    branch(repo, "pr1", {"a/BAD": "x"})
    branch(repo, "pr2", {"a/two.txt": "2"})
    branch(repo, "pr3", {"b/three.txt": "3"})
    report = run(repo, [step(1, ["a/**"]), step(2, ["a/**"], [1]), step(3, ["b/**"])])
    assert dropped(report) == {1: "gate_failed", 2: "depends_on_dropped"}
    assert report["integrated"] == [3]


def test_foreign_path_is_dropped(repo):
    branch(repo, "pr1", {"a/ok.txt": "1", "b/foreign.txt": "x"})
    report = run(repo, [step(1, ["a/**"])])
    assert dropped(report) == {1: "touches_foreign_paths"} and report["integrated"] == []


def test_merge_conflict_is_dropped_and_others_continue(repo):
    branch(repo, "pr1", {"a/base.txt": "one\n"})
    branch(repo, "pr2", {"a/base.txt": "two\n"})
    branch(repo, "pr3", {"b/three.txt": "3"})
    report = run(repo, [step(1, ["a/**"]), step(2, ["a/**"]), step(3, ["b/**"])])
    assert dropped(report) == {2: "gate_failed"}
    assert [d["failed_gate"] for d in report["dropped_prs"]] == ["merge"]
    assert report["integrated"] == [1, 3]


def test_prepare_runs_once_on_the_integration_tree_before_any_gate(repo):
    branch(repo, "pr1", {"a/one.txt": "1"})
    seen = []

    def prepare(tree):
        seen.append(("prepare", tree, (tree / "a/base.txt").exists()))

    def gates(tree, which):
        seen.append(("gates", tree))
        return gates_stub(tree, which)

    ig.integrate(repo, {"base": "main", "steps": [step(1, ["a/**"])]}, gates, ref_for=lambda pr: f"pr{pr}", prepare=prepare)
    assert seen[0][0] == "prepare" and [s[0] for s in seen].count("prepare") == 1
    assert seen[0][1] != repo and seen[0][2], "prepare must run on the throwaway tree, not on the base checkout"
    assert all(s[1] == seen[0][1] for s in seen)


def test_install_and_web_commands_point_at_the_integration_tree(tmp_path):
    cmds = ig.install_command(tmp_path, python="/venv/bin/python")
    assert cmds[:5] == ["uv", "pip", "install", "--python", "/venv/bin/python"]
    assert str(tmp_path / "packages/contracts") in cmds and str(tmp_path / "packages/testing") in cmds
    web = ig.web_commands(tmp_path)
    assert [c for c, _ in web] == [["npm", "ci", "--no-audit", "--no-fund"], ["npx", "playwright", "install", "chromium"]]
    assert all(cwd == tmp_path / "apps/web" for _, cwd in web)


def test_final_report_runs_all_six_gates(repo):
    branch(repo, "pr1", {"a/one.txt": "1"})
    report = run(repo, [step(1, ["a/**"])])
    assert report["overall"] == "pass" and len(report["gates"]) == 6
