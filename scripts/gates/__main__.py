"""`python -m gates` entry point (contracts/gate-runner-cli.md). Exit codes: 0 pass, 1 fail, 2 not run, 3 invalid input."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import audit_check, contracts_gate, integrate, integration_gate, isolation_gate, matrix, suite_gate, summary
from . import report as rep
from .validate import ROOT, validate

INTEGRATION = "docs/architecture/integration"


def _load(root: Path, name: str):
    path = root / INTEGRATION / name
    return json.loads(path.read_text()) if path.exists() else None


def make_runner(plan: dict | None, openapi: dict | None = None):
    """Returns run_gates(root, gates) used by `run` and by `integrate` (root is the tree under test)."""
    def run_gates(root: Path, gates) -> list[rep.GateResult]:
        matrix_doc = _load(root, "contract-matrix.json")
        ownership = matrix_doc["schema_ownership"] if matrix_doc else {}
        runners = {
            "contracts": lambda: contracts_gate.run(root, openapi=openapi),
            "isolation": lambda: isolation_gate.run(root, ownership, database=bool(os.environ.get("MMI_GATES_DATABASE"))),
            "integration": lambda: integration_gate.run(plan),
            "e2e": lambda: suite_gate.run("e2e", root),
            "security": lambda: suite_gate.run("security", root),
            "cost": lambda: suite_gate.run("cost", root),
        }
        return [runners[g]() for g in gates]
    return run_gates


def _write(path: str | None, report: dict) -> None:
    if path:
        Path(path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _print(report: dict) -> None:
    for g in report["gates"]:
        print(f"{g['gate']:12} {g['result']:8} {g['evidence'][0] if g['evidence'] else ''}")


def _cmd_validate(_args: argparse.Namespace) -> int:
    errors = validate(ROOT)
    for e in errors:
        print(e, file=sys.stderr)
    return 3 if errors else 0


def _cmd_matrix(args: argparse.Namespace) -> int:
    openapi = json.loads(Path(args.openapi).read_text()) if args.openapi else None
    print(matrix.write(ROOT, openapi))
    return 0


def _cmd_lookup(args: argparse.Namespace) -> int:
    doc = _load(ROOT, "contract-matrix.json")
    hits = matrix.lookup(doc, args.name) if doc else []
    if not hits:
        print(f"no interface named {args.name!r} in contract-matrix.json", file=sys.stderr)
        return 3
    for e in hits:
        print(f"{e['name']} v{e['version']} | {e['kind']} | owner: {e['owner']} | consumers: {', '.join(e['consumers']) or '-'} | status: {e['status']}")
    return 0


def _cmd_matrix_md(_args: argparse.Namespace) -> int:
    base = ROOT / INTEGRATION
    (base / "contract-matrix.md").write_text(matrix.render(json.loads((base / "contract-matrix.json").read_text())), encoding="utf-8")
    return 0


def _cmd_audit_md(_args: argparse.Namespace) -> int:
    base = ROOT / INTEGRATION
    (base / "feature-status.md").write_text(audit_check.render(json.loads((base / "feature-status.json").read_text())), encoding="utf-8")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    wanted = args.gate or list(rep.GATES)
    openapi = json.loads(Path(args.openapi).read_text()) if args.openapi else None
    report = rep.build_report(make_runner(_load(ROOT, "integration-plan.json"), openapi)(ROOT, wanted))
    _write(args.report, report)
    _print(report)
    return rep.exit_code(report)


def _cmd_integrate(args: argparse.Namespace) -> int:
    plan = json.loads(Path(args.plan).read_text())
    def prepare(tree: Path) -> None:
        """Installs that must come from the integration tree (T062, T063); each is a subprocess that fails the run loudly."""
        if args.install:
            subprocess.run(integrate.install_command(tree), check=True)  # noqa: S603
        if args.web:
            for cmd, cwd in integrate.web_commands(tree):
                subprocess.run(cmd, cwd=cwd, check=True)  # noqa: S603

    report = integrate.integrate(ROOT, plan, make_runner(None), prepare=prepare if (args.install or args.web) else None)
    # Integration status is only known after the run: account for every step, then recompute the aggregate.
    dropped = {d["pr"]: d for d in report.get("dropped_prs", [])}
    outcome = {**plan, "steps": [
        {**s, "state": "dropped", "drop_reason": f"{dropped[s['pr']]['reason']}: {dropped[s['pr']]['failed_gate']}"}
        if s["pr"] in dropped else {**s, "state": "integrated"} for s in plan["steps"]]}
    results = [rep.GateResult(**g) for g in report["gates"] if g["gate"] != "integration"]
    results.append(integration_gate.run(outcome))
    final = {**rep.build_report(results, list(dropped.values())), "integrated": report["integrated"]}
    _write(args.report, final)
    _print(final)
    return rep.exit_code(final)


def _cmd_summary(args: argparse.Namespace) -> int:
    print(summary.render(json.loads(Path(args.report).read_text()), args.pr), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gates")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate").set_defaults(func=_cmd_validate)
    mx = sub.add_parser("matrix", help="regenerate contract-matrix.json from packages/contracts (endpoints kept, or refreshed from --openapi)")
    mx.add_argument("--openapi", help="the gateway's exported openapi.json")
    mx.set_defaults(func=_cmd_matrix)
    sub.add_parser("matrix-md", help="render contract-matrix.json to contract-matrix.md").set_defaults(func=_cmd_matrix_md)
    lk = sub.add_parser("lookup", help="print owner, version, consumers and status of an interface; exit 3 if unknown")
    lk.add_argument("name", help="a schema name (money), a versioned name (money.v1) or an endpoint name ('GET /api/dashboard/overview')")
    lk.set_defaults(func=_cmd_lookup)
    sub.add_parser("audit-md", help="render feature-status.json to feature-status.md").set_defaults(func=_cmd_audit_md)
    run = sub.add_parser("run")
    run.add_argument("--gate", action="append", choices=rep.GATES)
    run.add_argument("--report")
    run.add_argument("--openapi", help="the gateway's exported openapi.json: also checks the matrix's endpoint entries")
    run.set_defaults(func=_cmd_run)
    integ = sub.add_parser("integrate", help="build a temporary integration tree from the plan and run all gates on it")
    integ.add_argument("--plan", default=str(ROOT / INTEGRATION / "integration-plan.json"))
    integ.add_argument("--report")
    integ.add_argument("--install", action="store_true", help="install packages/contracts and packages/testing from the integration tree")
    integ.add_argument("--web", action="store_true", help="run npm ci and install Chromium in the integration tree's apps/web")
    integ.set_defaults(func=_cmd_integrate)
    summ = sub.add_parser("summary", help="print a Markdown summary of a gate report")
    summ.add_argument("--report", required=True)
    summ.add_argument("--pr", type=int)
    summ.set_defaults(func=_cmd_summary)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
