"""Contracts gate (T015): the matrix must describe every shared schema, and changes must stay compatible.

Rules: every schema file has a matrix entry and every non-endpoint entry points to a file; a schema
changed against ``packages/contracts/baseline`` may only be additive; a deprecated entry names its
successor and every consumer has moved to it before the old version can go (spec FR-004/FR-005).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .report import GateResult, utc_now

CONTRACTS = Path("packages/contracts")
NAME = re.compile(r"^(?P<name>.+)\.v(?P<version>[0-9]+)\.schema\.json$")


def breaking(old: dict, new: dict, path: str = "") -> list[str]:
    """Same additive-only rule as packages/contracts/tests/test_compat.py (kept in sync there)."""
    problems: list[str] = []
    for key, spec in old.get("properties", {}).items():
        if key not in new.get("properties", {}):
            problems.append(f"{path}{key}: removed")
            continue
        n = new["properties"][key]
        if spec.get("type") != n.get("type") and "$ref" not in spec:
            problems.append(f"{path}{key}: type changed")
        if "enum" in spec and not set(spec["enum"]) <= set(n.get("enum", spec["enum"])):
            problems.append(f"{path}{key}: enum narrowed")
        if spec.get("type") == "object":
            problems += breaking(spec, n, f"{path}{key}.")
    added = set(new.get("required", [])) - set(old.get("required", []))
    if added:
        problems.append(f"{path}new required: {sorted(added)}")
    for name, sub in old.get("$defs", {}).items():
        if name in new.get("$defs", {}):
            problems += breaking(sub, new["$defs"][name], f"{path}${name}.")
    return problems


def schema_files(root: Path) -> dict[str, tuple[str, str, int]]:
    """schema_path (relative to packages/contracts) -> (kind, name, version)."""
    found: dict[str, tuple[str, str, int]] = {}
    for sub, kind in (("dto", "dto"), ("events", "event")):
        for f in sorted((root / CONTRACTS / sub).glob("*.schema.json")):
            m = NAME.match(f.name)
            if m:
                found[f"{sub}/{f.name}"] = (kind, m["name"], int(m["version"]))
    if (root / CONTRACTS / "errors/error_codes.json").exists():
        found["errors/error_codes.json"] = ("error", "error_codes", 1)
    return found


def check(root: Path, matrix: dict) -> list[str]:
    problems: list[str] = []
    entries = matrix["entries"]
    by_path = {e["schema_path"]: e for e in entries if "schema_path" in e}
    by_key = {f"{e['name']}.v{e['version']}": e for e in entries}
    for path, (kind, name, version) in schema_files(root).items():
        e = by_path.get(path)
        if not e:
            problems.append(f"{path}: no matrix entry")
        elif (e["kind"], e["name"], e["version"]) != (kind, name, version):
            problems.append(f"{path}: matrix entry says {e['kind']} {e['name']} v{e['version']}")
    for e in entries:
        if "schema_path" in e and not (root / CONTRACTS / e["schema_path"]).exists():
            problems.append(f"{e['name']}.v{e['version']}: schema file {e['schema_path']} not found")
        if e["status"] == "deprecated":
            succ = by_key.get(e.get("superseded_by", ""))
            if not succ:
                problems.append(f"{e['name']}.v{e['version']}: successor {e.get('superseded_by')!r} not in matrix")
                continue
            unmoved = sorted(set(e["consumers"]) - set(succ["consumers"]))
            if unmoved:
                problems.append(f"{e['name']}.v{e['version']}: consumers not on successor: {unmoved}")
    baseline = root / CONTRACTS / "baseline"
    for old_file in sorted(baseline.glob("*/*.schema.json")):
        current = root / CONTRACTS / old_file.parent.name / old_file.name
        if not current.exists():
            problems.append(f"{old_file.name}: removed; a breaking change needs a new versioned file")
            continue
        old, new = json.loads(old_file.read_text()), json.loads(current.read_text())
        problems += [f"{old_file.name}: {p}" for p in breaking(old, new)]
    return problems


HTTP = ("get", "post", "put", "patch", "delete")


def endpoint_names(openapi: dict) -> set[str]:
    return {f"{method.upper()} {path}" for path, ops in openapi["paths"].items() for method in HTTP if method in ops}


def check_endpoints(matrix: dict, openapi: dict) -> list[str]:
    """The gateway's endpoints (from its exported OpenAPI) and the matrix's `endpoint` entries must agree (T055)."""
    live = endpoint_names(openapi)
    listed = {e["name"] for e in matrix["entries"] if e["kind"] == "endpoint"}
    return [*(f"{n}: no matrix entry" for n in sorted(live - listed)),
            *(f"{n}: in the matrix but not in the gateway" for n in sorted(listed - live))]


def run(root: Path, matrix_path: Path | None = None, openapi: dict | None = None) -> GateResult:
    started = utc_now()
    matrix_path = matrix_path or root / "docs/architecture/integration/contract-matrix.json"
    if not matrix_path.exists():
        return GateResult("contracts", "not_run", [f"{matrix_path.name} not found"], started)
    matrix = json.loads(matrix_path.read_text())
    problems = check(root, matrix) + (check_endpoints(matrix, openapi) if openapi else [])
    note = "matrix and schemas agree" + ("" if openapi else "; endpoints not checked (no openapi supplied; the api-bff test covers them)")
    return GateResult("contracts", "fail" if problems else "pass", problems or [note], started)
