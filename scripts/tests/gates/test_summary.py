"""T040: Markdown summary of a gate report for the PR comment."""

from __future__ import annotations

from gates import report as r
from gates import summary as s


def _report(dropped=None, integrated=None):
    results = [r.GateResult(g, "pass", ["ok"]) for g in r.GATES]
    results[5] = r.GateResult("cost", "fail", ["FAILED infra/tests/test_cost_guardrails.py::test_x - assert False", "second line"])
    rep = r.build_report(results, dropped)
    if integrated is not None:
        rep["integrated"] = integrated
    return rep


def test_lists_every_gate_with_result_and_duration():
    md = s.render(_report())
    assert all(f"| {g} |" in md for g in r.GATES)
    assert "overall: **fail**" in md and "s |" in md


def test_evidence_is_first_line_only_and_short():
    md = s.render(_report())
    assert "second line" not in md
    assert all(len(line) < 300 for line in md.splitlines())


def test_untrusted_report_text_cannot_inject_mentions_links_or_html():
    nasty = "@octocat [click](http://evil.example) <img src=x> `code`\nsecond"
    dropped = [{"pr": 7, "agent": "@octocat", "reason": "gate_failed", "failed_gate": "[x](y)"}]
    rep = r.build_report([r.GateResult(g, "pass", [nasty]) for g in r.GATES], dropped)
    md = s.render(rep) + s.render(rep, pr=7)
    assert "@" not in md and "](" not in md and "<" not in md and "`code`" not in md and "second" not in md


def test_dropped_prs_are_listed_and_filtered_by_pr():
    dropped = [{"pr": 7, "agent": "agent-01", "reason": "gate_failed", "failed_gate": "cost"},
               {"pr": 8, "agent": "agent-02", "reason": "depends_on_dropped", "failed_gate": "cost"}]
    rep = _report(dropped, integrated=[9])
    assert "| 7 |" in s.render(rep) and "| 8 |" in s.render(rep)
    only7 = s.render(rep, pr=7)
    assert "PR 7" in only7 and "gate_failed" in only7 and "| 8 |" not in only7
    assert "PR 9" in s.render(rep, pr=9) and "integrated" in s.render(rep, pr=9)
    assert "not part of this run" in s.render(rep, pr=99)
