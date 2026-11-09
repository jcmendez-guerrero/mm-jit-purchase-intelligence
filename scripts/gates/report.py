"""Gate results, aggregation and exit codes (spec FR-009/FR-010, contracts/gate-runner-cli.md)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

GATES = ("contracts", "isolation", "integration", "e2e", "security", "cost")
EXIT = {"pass": 0, "fail": 1, "not_run": 2}
_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def utc_now() -> str:
    return datetime.now(UTC).strftime(_FMT)


@dataclass
class GateResult:
    gate: str
    result: str  # pass | fail | not_run
    evidence: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def __post_init__(self) -> None:
        if self.gate not in GATES:
            raise ValueError(f"unknown gate {self.gate!r}")
        if self.result not in EXIT:
            raise ValueError(f"unknown result {self.result!r}")
        self.started_at = self.started_at or utc_now()
        self.finished_at = self.finished_at or utc_now()


def seconds(entry: dict) -> float:
    """Duration of one gate entry (SC-008); the original timestamp strings stay in the report."""
    start = datetime.fromisoformat(entry["started_at"])  # any ISO 8601 form the report schema allows, including a trailing Z
    end = datetime.fromisoformat(entry["finished_at"])
    return (end - start).total_seconds()


def overall(results: list[GateResult]) -> str:
    """fail beats not_run beats pass; a gate that is missing counts as not run."""
    by_gate = {r.gate: r.result for r in results}
    states = [by_gate.get(g, "not_run") for g in GATES]
    if "fail" in states:
        return "fail"
    return "not_run" if "not_run" in states else "pass"


def build_report(results: list[GateResult], dropped_prs: list[dict] | None = None) -> dict:
    present = {r.gate for r in results}
    filled = [*results, *(GateResult(g, "not_run", ["gate was not run"]) for g in GATES if g not in present)]
    filled.sort(key=lambda r: GATES.index(r.gate))
    report: dict = {"overall": overall(filled), "gates": [asdict(r) for r in filled]}
    if dropped_prs:
        report["dropped_prs"] = dropped_prs
    return report


def exit_code(report: dict) -> int:
    return EXIT[report["overall"]]
