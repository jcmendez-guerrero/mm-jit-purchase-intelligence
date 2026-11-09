"""Platform guarantee to test map (T036/T037, spec FR-013): every guarantee must name an existing test file."""

from __future__ import annotations

import re
from pathlib import Path

MAP = Path("docs/architecture/integration/guarantee-test-map.md")
REQUIRED = (
    "Role-based access", "Second factor for sensitive operations", "Audit trail", "UTC timestamps", "Decimal money",
)
PATH = re.compile(r"`([\w./-]+/test_[\w]+\.py)`")


def _rows(root: Path) -> list[str]:
    f = root / MAP
    return [line for line in f.read_text(encoding="utf-8").splitlines() if line.startswith("|")] if f.exists() else []


def mapped_tests(root: Path) -> list[str]:
    seen: list[str] = []
    for row in _rows(root):
        seen += [p for p in PATH.findall(row) if p not in seen]
    return seen


def check(root: Path) -> list[str]:
    problems: list[str] = []
    rows = _rows(root)
    if not rows:
        return [f"{MAP}: missing or without a table"]
    for name in REQUIRED:
        row = next((r for r in rows if r.split("|")[1].strip().startswith(name)), None)
        paths = PATH.findall(row) if row else []
        if not paths:
            problems.append(f"{name}: no covering test in {MAP}")
        problems += [f"{name}: test file missing: {p}" for p in paths if not (root / p).is_file()]
    return problems
