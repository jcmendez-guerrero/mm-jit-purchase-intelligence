"""T031: suite gate wrapper, with a stub runner (no real suites are started)."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from gates import suite_gate as s


def stub(rc=0, out="", err="", raises=None):
    def runner(argv, **kw):
        if raises:
            raise raises
        return SimpleNamespace(returncode=rc, stdout=out, stderr=err)
    return runner


def run(cmds, runner, root, environ=None):
    return s.run_commands("e2e", cmds, root, runner=runner, environ=environ or {})


def test_all_commands_passing(tmp_path):
    r = run([s.Cmd(("pytest",))], stub(0), tmp_path)
    assert r.result == "pass"


def test_failing_command_is_fail_with_failed_lines(tmp_path):
    out = "...\nFAILED infra/tests/test_x.py::test_a - assert 1 == 2\n1 failed in 0.1s\n"
    r = run([s.Cmd(("pytest",))], stub(1, out), tmp_path)
    assert r.result == "fail" and any("FAILED infra/tests/test_x.py::test_a" in e for e in r.evidence)


def test_unrunnable_tool_is_not_run(tmp_path):
    r = run([s.Cmd(("npm", "run", "e2e"))], stub(raises=FileNotFoundError()), tmp_path)
    assert r.result == "not_run" and "npm" in r.evidence[0]


def recorder(codes=None):
    """Stub runner that records every argv and returns the exit code for the first matching keyword."""
    calls = []

    def runner(argv, **kw):
        calls.append(argv)
        rc = next((c for key, c in (codes or {}).items() if key in argv), 0)
        return SimpleNamespace(returncode=rc, stdout="", stderr="")
    runner.calls = calls
    return runner


def _live(tmp_path, runner, which=lambda t: "/usr/bin/" + t):
    (tmp_path / "infra").mkdir(exist_ok=True)
    (tmp_path / "infra/compose.yaml").write_text("")
    (tmp_path / "apps/web").mkdir(parents=True, exist_ok=True)
    (tmp_path / "apps/web/package.json").write_text("{}")
    (tmp_path / "apps/web/playwright.live.config.ts").write_text("")
    return s.run("e2e", tmp_path, runner=runner, environ={"MMI_GATES_LIVE_STACK": "1"}, which=which)


def test_live_stack_is_brought_up_before_the_journey_and_always_torn_down(tmp_path):
    runner = recorder({"playwright": 1})  # the journey fails
    result = _live(tmp_path, runner)
    verbs = [next(a for a in c if a in ("up", "down")) for c in runner.calls if "compose" in c]
    assert verbs == ["up", "down"], "the stack must come down even when the journey fails"
    assert result.result == "fail"
    journey = next(c for c in runner.calls if "playwright.live.config.ts" in " ".join(c))
    assert journey  # the live journey ran against the stack


def test_live_stack_that_does_not_start_fails_without_running_the_journey_and_still_cleans_up(tmp_path):
    runner = recorder({"up": 1})
    result = _live(tmp_path, runner)
    assert result.result == "fail" and "live stack" in result.evidence[0]
    assert not any("playwright.live.config.ts" in " ".join(c) for c in runner.calls)
    assert any("down" in c for c in runner.calls)


def test_without_the_flag_no_stack_is_started(tmp_path):
    runner = recorder()
    s.run("e2e", tmp_path, runner=runner, environ={})
    assert not any("compose" in c for c in runner.calls)


def test_every_gate_has_its_own_time_limit_and_the_runner_receives_it(tmp_path):
    from gates.report import GATES

    assert set(s.TIMEOUTS) == set(GATES) and all(isinstance(v, int) and v > 0 for v in s.TIMEOUTS.values())
    seen = {}

    def runner(argv, **kw):
        seen["timeout"] = kw["timeout"]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    for gate in ("cost", "e2e"):
        s.run_commands(gate, [s.Cmd(("x",))], tmp_path, runner=runner, environ={})
        assert seen["timeout"] == s.TIMEOUTS[gate]
    assert s.TIMEOUTS["cost"] < s.TIMEOUTS["e2e"]


def test_command_not_found_exit_127_is_not_run_not_fail(tmp_path):
    r = run([s.Cmd(("npm", "run", "e2e"))], stub(127, err="sh: playwright: command not found"), tmp_path)
    assert r.result == "not_run" and "127" in r.evidence[0]


def test_missing_required_tool_is_not_run(tmp_path):
    r = run([s.Cmd(("x",), requires_tools=("definitely-not-an-installed-tool",))], stub(0), tmp_path)
    assert r.result == "not_run" and "definitely-not-an-installed-tool" in r.evidence[0]


def test_a_pytest_run_where_everything_was_skipped_is_not_run_not_pass(tmp_path):
    assert run([s.Cmd(("pytest",))], stub(0, "6 skipped in 0.1s"), tmp_path).result == "not_run"
    assert run([s.Cmd(("pytest",))], stub(0, "5 passed, 1 skipped in 2s"), tmp_path).result == "pass"


def test_missing_path_or_env_is_not_run(tmp_path):
    assert run([s.Cmd(("x",), requires_paths=("nope.py",))], stub(0), tmp_path).result == "not_run"
    assert run([s.Cmd(("x",), requires_env=("PLAYWRIGHT_BASE_URL",))], stub(0), tmp_path).result == "not_run"
    assert run([s.Cmd(("x",), requires_env=("PLAYWRIGHT_BASE_URL",))], stub(0), tmp_path, {"PLAYWRIGHT_BASE_URL": "http://localhost"}).result == "pass"


def test_fail_beats_not_run_and_timeouts_fail(tmp_path):
    cmds = [s.Cmd(("a",), requires_paths=("nope",)), s.Cmd(("b",))]
    assert run(cmds, stub(1, "boom"), tmp_path).result == "fail"
    assert run([s.Cmd(("a",))], stub(raises=subprocess.TimeoutExpired("a", 1)), tmp_path).result == "fail"


def test_evidence_is_short_and_has_no_full_output(tmp_path):
    r = run([s.Cmd(("pytest",))], stub(1, "secret-looking-row " * 500), tmp_path)
    assert all(len(e) < 400 for e in r.evidence)


def test_every_suite_is_defined_for_the_three_wrapped_gates(tmp_path):
    for gate in ("e2e", "security", "cost"):
        assert s.suite(gate, tmp_path) and all(isinstance(c, s.Cmd) for c in s.suite(gate, tmp_path))
