"""Markdown summary of a gate report, posted by CI as a comment on each domain PR (T041, ADR-022).

Contains gate names, results, durations, PR numbers and the first evidence line only; no data values.
"""

from __future__ import annotations

import re

from .report import seconds


def clean(text: object, limit: int = 120) -> str:
    """The report is untrusted data (T054): one line, no mentions, links, HTML, code spans or table breaks."""
    first = str(text).splitlines()[0] if str(text).strip() else ""
    return re.sub(r"[@<>\[\]`|]", " ", first)[:limit].strip()


def render(report: dict, pr: int | None = None) -> str:
    lines = [f"### Gate report (overall: **{report['overall']}**)", "", "| Gate | Result | Time | Evidence |", "|---|---|---|---|"]
    for g in report["gates"]:
        first = clean(g["evidence"][0] if g["evidence"] else "")
        try:
            took = f"{seconds(g):.1f}s"
        except (KeyError, TypeError, ValueError):  # the report is untrusted: an unreadable time must not stop the comment
            took = "-"
        lines.append(f"| {clean(g['gate'])} | {clean(g['result'])} | {took} | {first} |")
    dropped = report.get("dropped_prs", [])
    if pr is None:
        if dropped:
            lines += ["", "Dropped PRs", "", "| PR | Agent | Reason | Failed gate |", "|---|---|---|---|",
                      *(f"| {int(d['pr'])} | {clean(d['agent'])} | {clean(d['reason'])} | {clean(d['failed_gate'])} |" for d in dropped)]
        return "\n".join(lines) + "\n"
    mine = next((d for d in dropped if d["pr"] == pr), None)
    if mine:
        lines += ["", f"PR {pr} was dropped: {clean(mine['reason'])} (failed gate: {clean(mine['failed_gate'])}). Fix it within your own files; it re-enters the next run."]
    elif pr in report.get("integrated", []):
        lines += ["", f"PR {pr} is integrated."]
    else:
        lines += ["", f"PR {pr} is not part of this run."]
    return "\n".join(lines) + "\n"
