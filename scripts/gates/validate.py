"""Validate the integration artifacts against their schemas (T005, T009, T029)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema

from . import audit_check

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = Path("docs/architecture/integration")
SPEC_CONTRACTS = Path("specs/005-architecture-contracts-integration/contracts")
ARTIFACTS = {
    "feature-status.json": "feature-status.schema.json",
    "contract-matrix.json": "contract-matrix.schema.json",
    "integration-plan.json": "integration-plan.schema.json",
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def plan_errors(plan: dict) -> list[str]:
    """Semantic checks the schema cannot express: unique PRs, known dependencies, no cycles."""
    steps = {s["pr"]: s for s in plan.get("steps", [])}
    errors = []
    if len(steps) != len(plan.get("steps", [])):
        errors.append("duplicate pr number in steps")
    for pr, step in steps.items():
        for dep in step["depends_on"]:
            if dep not in steps:
                errors.append(f"pr {pr} depends on unknown pr {dep}")
    state: dict[int, int] = {}

    def visit(pr: int) -> bool:
        if state.get(pr) == 1:
            return True
        if state.get(pr) == 2:
            return False
        state[pr] = 1
        cyclic = any(visit(d) for d in steps[pr]["depends_on"] if d in steps)
        state[pr] = 2
        return cyclic

    if any(visit(pr) for pr in steps):
        errors.append("dependency cycle in steps")
    errors += _overlaps(list(steps.values()))
    return errors


def _prefix(pattern: str) -> str:
    return re.split(r"[*?\[]", pattern, maxsplit=1)[0]


def _overlap(p: str, q: str) -> bool:
    """Conservative: patterns overlap when the fixed parts of their paths nest; two plain files overlap only when equal."""
    if not any(c in p + q for c in "*?["):
        return p == q
    a, b = _prefix(p), _prefix(q)
    return a.startswith(b) or b.startswith(a)


def _overlaps(steps: list[dict]) -> list[str]:
    """A path must have one owner (US3/AC3): different agents may not claim overlapping paths."""
    found = []
    for i, s in enumerate(steps):
        for t in steps[i + 1:]:
            if s["agent"] != t["agent"] and any(_overlap(p, q) for p in s["owned_paths"] for q in t["owned_paths"]):
                found.append(f"owned paths overlap between pr {s['pr']} ({s['agent']}) and pr {t['pr']} ({t['agent']})")
    return found


def schema_copy_errors(root: Path) -> list[str]:
    """The validated copies under docs/ must equal the design copies in the spec folder (D1)."""
    spec_dir = root / SPEC_CONTRACTS
    if not spec_dir.exists():
        return []
    errors = []
    for design in sorted(spec_dir.glob("*.schema.json")):
        copy = root / INTEGRATION / "schemas" / design.name
        if not copy.exists():
            errors.append(f"{design.name}: missing validated copy")
        elif _load(copy) != _load(design):
            errors.append(f"{design.name}: validated copy differs from design copy")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    errors = schema_copy_errors(root)
    for artifact, schema_name in ARTIFACTS.items():
        path = root / INTEGRATION / artifact
        schema_path = root / INTEGRATION / "schemas" / schema_name
        if not path.exists():
            errors.append(f"{artifact}: missing")
            continue
        validator = jsonschema.Draft202012Validator(_load(schema_path))
        data = _load(path)
        found = [f"{artifact}: {e.message}" for e in validator.iter_errors(data)]
        if not found and artifact == "integration-plan.json":  # semantic checks only on a schema-valid file, and only on its own errors
            found = [f"{artifact}: {m}" for m in plan_errors(data)]
        if not found and artifact == "feature-status.json":
            found = [f"{artifact}: {m}" for m in audit_check.check(root, data)]
        errors += found
    return errors
