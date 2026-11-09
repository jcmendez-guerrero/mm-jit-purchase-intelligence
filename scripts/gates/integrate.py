"""Build a temporary integration tree from the domain PRs and run the gates on it (T023, spec FR-008/FR-010).

Never pushes and never touches the base branch: merges happen in a detached throwaway worktree that is
removed afterwards. A PR that fails a gate, conflicts, or touches paths it does not own is dropped together
with the PRs that depend on it, and integration continues with the rest. The caller must have fetched the
PR heads already (CI fetches `refs/pull/*/head`); this module does no network access.
"""

from __future__ import annotations

import fnmatch
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from .report import GATES, GateResult, build_report

RunGates = Callable[[Path, list[str] | tuple[str, ...]], list[GateResult]]
IDENT = ["-c", "user.name=mmi-gates", "-c", "user.email=gates@example.test"]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *IDENT, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout  # noqa: S603, S607


def order(steps: list[dict]) -> list[dict]:
    """Dependencies first, otherwise the plan's own order."""
    by_pr = {s["pr"]: s for s in steps}
    done: list[dict] = []
    seen: set[int] = set()

    def visit(s: dict, stack: tuple[int, ...] = ()) -> None:
        if s["pr"] in seen:
            return
        if s["pr"] in stack:
            raise ValueError(f"dependency cycle at pr {s['pr']}")
        for d in s["depends_on"]:
            visit(by_pr[d], (*stack, s["pr"]))
        seen.add(s["pr"])
        done.append(s)

    for s in steps:
        visit(s)
    return done


def _owned(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def install_command(tree: Path, python: str = sys.executable) -> list[str]:
    """Editable install of the shared packages from the integration tree, so the gates import the merged code (T062)."""
    return ["uv", "pip", "install", "--python", python, "-e", str(tree / "packages/contracts"), "-e", str(tree / "packages/testing")]


def web_commands(tree: Path) -> list[tuple[list[str], Path]]:
    """What the browser suites need in the integration tree's apps/web (T063): dependencies and the Chromium build."""
    web = tree / "apps/web"
    return [(["npm", "ci", "--no-audit", "--no-fund"], web), (["npx", "playwright", "install", "chromium"], web)]


def integrate(root: Path, plan: dict, run_gates: RunGates, ref_for: Callable[[int], str] = lambda pr: f"refs/pull/{pr}/head",
              prepare: Callable[[Path], None] | None = None) -> dict:
    """`prepare(tree)` runs once on the throwaway tree before any merge, for installs that must come from that tree."""
    base = plan["base"]
    dropped: dict[int, dict] = {}
    integrated: list[int] = []
    tree = Path(tempfile.mkdtemp(prefix="mmi-integration-"))
    _git(root, "worktree", "add", "--detach", "--quiet", str(tree), base)
    try:
        if prepare:
            prepare(tree)
        for s in order(plan["steps"]):
            pr, agent = s["pr"], s["agent"]
            cause = next((dropped[d] for d in s["depends_on"] if d in dropped), None)
            if cause:
                dropped[pr] = {"pr": pr, "agent": agent, "reason": "depends_on_dropped", "failed_gate": cause["failed_gate"]}
                continue
            ref = ref_for(pr)
            changed = _git(root, "diff", "--name-only", f"{base}...{ref}").split()
            if any(not _owned(p, s["owned_paths"]) for p in changed):
                dropped[pr] = {"pr": pr, "agent": agent, "reason": "touches_foreign_paths", "failed_gate": "ownership"}
                continue
            try:
                _git(tree, "merge", "--no-ff", "--no-edit", "--quiet", ref)
            except subprocess.CalledProcessError:
                subprocess.run(["git", "merge", "--abort"], cwd=tree, check=False, capture_output=True)  # noqa: S603, S607
                dropped[pr] = {"pr": pr, "agent": agent, "reason": "gate_failed", "failed_gate": "merge"}
                continue
            failing = next((r.gate for r in run_gates(tree, s["verification"]) if r.result == "fail"), None)
            if failing:
                _git(tree, "reset", "--hard", "--quiet", "HEAD~1")
                dropped[pr] = {"pr": pr, "agent": agent, "reason": "gate_failed", "failed_gate": failing}
                continue
            integrated.append(pr)
        final = build_report(run_gates(tree, GATES), list(dropped.values()))
    finally:
        _git(root, "worktree", "remove", "--force", str(tree))
    final["integrated"] = integrated
    return final
