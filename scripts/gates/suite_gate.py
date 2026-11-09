"""Wrap the existing end-to-end, security and cost suites as gates (T034/T038/T039).

A command that cannot start (tool missing, required file or environment variable absent) makes the gate
`not_run`; a command that exits non-zero makes it `fail`. Evidence holds only the failing test ids or the last
output line, never full output. The wrapped suites are the existing ones; nothing is re-implemented here.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import guarantees
from .report import GateResult, utc_now

PY = sys.executable
# Per-gate limits (SC-008), set from the first clean full run on a developer machine with warm caches:
# contracts 0.2 s, isolation with the database check 40 s, e2e with the live stack 84 s, security 28 s, cost 1 s.
# Each limit is roughly 7 to 15 times that, to leave room for a cold CI runner (image pulls and builds).
TIMEOUTS = {"contracts": 120, "isolation": 600, "integration": 120, "e2e": 1200, "security": 600, "cost": 120}


@dataclass(frozen=True)
class Cmd:
    argv: tuple[str, ...]
    cwd: str = "."
    env: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    requires_env: tuple[str, ...] = ()
    requires_paths: tuple[str, ...] = ()
    requires_tools: tuple[str, ...] = ()


def _evidence(cmd: Cmd, rc: int, output: str) -> str:
    failed = [ln.strip() for ln in output.splitlines() if ln.startswith("FAILED ")][:5]
    last = next((ln.strip() for ln in reversed(output.splitlines()) if ln.strip()), "no output")
    detail = "; ".join(failed) if failed else last
    return f"{' '.join(cmd.argv)[:80]} exited {rc}: {detail}"[:380]


SKIPPED_ONLY = re.compile(r"\b\d+ skipped\b")
PASSED = re.compile(r"\b\d+ passed\b")


def run_commands(gate: str, cmds: list[Cmd], root: Path, runner: Callable = subprocess.run,
                 environ: dict | None = None, which: Callable = shutil.which) -> GateResult:
    environ = os.environ if environ is None else environ
    started = utc_now()
    failures: list[str] = []
    skipped: list[str] = []
    for cmd in cmds:
        missing = [p for p in cmd.requires_paths if not (root / p).exists()]
        absent = [v for v in cmd.requires_env if not environ.get(v)] + [t for t in cmd.requires_tools if not which(t)]
        if missing or absent:
            skipped.append(f"{cmd.argv[0]}: needs {', '.join(missing + absent)}")
            continue
        try:
            # COLUMNS: pytest cuts its short summary to the terminal width, which would drop the failure message
            proc = runner(list(cmd.argv), cwd=root / cmd.cwd, env={**os.environ, **environ, "COLUMNS": "400", **dict(cmd.env)}, capture_output=True,
                          text=True, timeout=TIMEOUTS[gate], check=False)
        except FileNotFoundError:
            skipped.append(f"{cmd.argv[0]} is not installed")
            continue
        except subprocess.TimeoutExpired:
            failures.append(f"{' '.join(cmd.argv)[:80]} timed out")
            continue
        if proc.returncode == 127:  # shell: command not found, so the tooling is missing, not the code under test broken
            skipped.append(_evidence(cmd, 127, (proc.stdout or "") + (proc.stderr or "")))
            continue
        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0 and SKIPPED_ONLY.search(output) and not PASSED.search(output):
            skipped.append(f"{cmd.argv[0]}: every test was skipped (a prerequisite is missing)")  # a skipped run proves nothing
            continue
        if proc.returncode != 0:
            failures.append(_evidence(cmd, proc.returncode, output))
    if failures:
        return GateResult(gate, "fail", failures + skipped, started)
    if skipped:
        return GateResult(gate, "not_run", skipped, started)
    return GateResult(gate, "pass", [f"{len(cmds)} command(s) passed"], started)


def _pytest(*paths: str, env: tuple[tuple[str, str], ...] = ()) -> Cmd:
    return Cmd((PY, "-m", "pytest", "-q", "-rf", *paths), env=env, requires_paths=paths)


def _per_package(tests: list[str]) -> list[Cmd]:
    """One pytest process per service: services share top-level module names (`db`, `main`) and cannot be collected together."""
    groups: dict[str, list[str]] = {}
    for t in tests:
        parts = t.split("/")
        key = "/".join(parts[:2]) if parts[0] in ("services", "packages") else "."
        groups.setdefault(key, []).append(t if key == "." else "/".join(parts[2:]))
    return [Cmd((PY, "-m", "pytest", "-q", "-rf", *rel), cwd=key,
                requires_paths=tuple(r if key == "." else f"{key}/{r}" for r in rel)) for key, rel in groups.items()]


def suite(gate: str, root: Path) -> list[Cmd]:
    if gate == "e2e":
        return [
            _pytest("infra/tests/test_pipeline_e2e.py", "infra/tests/test_approval_e2e.py", env=(("RUN_E2E", "1"),)),
            Cmd(("npm", "run", "e2e", "--", "--trace", "off"), cwd="apps/web", requires_paths=("apps/web/package.json",)),
            # The real-services Spanish UI journey (FR-011): needs the local compose stack up and its URL exported.
            Cmd(("npx", "playwright", "test", "--config", "playwright.live.config.ts"), cwd="apps/web",
                requires_env=("PLAYWRIGHT_BASE_URL",), requires_paths=("apps/web/playwright.live.config.ts",)),
        ]
    if gate == "security":
        tests = list(dict.fromkeys([*guarantees.mapped_tests(root), "infra/tests/test_security_abuse.py",
                                    "infra/tests/test_erp_boundary.py", "infra/tests/test_web_headers.py"]))
        return [*_per_package(tests), Cmd((PY, "scripts/check_export_signatures.py"), requires_paths=("scripts/check_export_signatures.py",))]
    if gate == "cost":
        return [_pytest("infra/tests/test_cost_guardrails.py", "infra/tests/test_alert_rules.py")]
    raise ValueError(f"no suite for gate {gate!r}")


LIVE_PROJECT = "mmi-gates-live"   # its own compose project name, so it never touches another running stack
LIVE_URL = "http://localhost:8080"   # the web port published by infra/compose.yaml


def _compose(*args: str) -> Cmd:
    return Cmd(("docker", "compose", "-p", LIVE_PROJECT, "-f", "infra/compose.yaml", *args), requires_tools=("docker",),
               requires_paths=("infra/compose.yaml",))


def run(gate: str, root: Path, runner: Callable = subprocess.run, environ: dict | None = None,
        which: Callable = shutil.which) -> GateResult:
    """With MMI_GATES_LIVE_STACK=1 the e2e gate first starts the compose stack (web and what it needs), points the live
    journey at it through PLAYWRIGHT_BASE_URL, and always removes the stack afterwards (T063, FR-011)."""
    environ = os.environ if environ is None else environ
    problems = guarantees.check(root) if gate == "security" else []
    live = gate == "e2e" and bool(environ.get("MMI_GATES_LIVE_STACK"))
    down = lambda: run_commands(gate, [_compose("down", "-v", "--remove-orphans")], root, runner, environ, which)  # noqa: E731
    if live:
        up = run_commands(gate, [_compose("up", "-d", "--build", "--wait", "--wait-timeout", "600", "web")], root, runner, environ, which)
        if up.result != "pass":
            down()
            return GateResult(gate, "not_run" if up.result == "not_run" else "fail", [f"live stack: {e}" for e in up.evidence], up.started_at)
        environ = {**environ, "PLAYWRIGHT_BASE_URL": LIVE_URL}
    try:
        result = run_commands(gate, suite(gate, root), root, runner, environ, which)
    finally:
        if live:
            down()
    if problems:
        return GateResult(gate, "fail", [*problems, *result.evidence], result.started_at)
    return result
