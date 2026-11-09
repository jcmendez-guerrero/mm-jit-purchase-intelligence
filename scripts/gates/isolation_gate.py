"""Schema-isolation gate (T016): a service may reference only its own database schema (spec FR-006).

Static scan of SQL-looking text in ``services/<service>/`` (migrations and source). It is offline and
cheap; role grants are checked separately by the PostgreSQL migration test.
shortcut: regex scan, not a SQL parser; upgrade to a parser if false negatives appear.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from . import suite_gate
from .report import GateResult, utc_now

SUFFIXES = {".py", ".sql", ".ini", ".mako"}
SKIP = {"tests", "__pycache__", "node_modules"}


def _patterns(foreign: list[str]) -> list[re.Pattern[str]]:
    names = "|".join(re.escape(s) for s in foreign)
    return [
        re.compile(rf"\b(?:from|join|into|update|table|references)\s+\"?(?P<s>{names})\"?\.\w", re.I),
        re.compile(rf"ForeignKey\(\s*[\"'](?P<s>{names})\.\w", re.I),
        re.compile(rf"[\"']schema[\"']\s*:\s*[\"'](?P<s>{names})[\"']", re.I),
        re.compile(rf"\bschema\s*=\s*[\"'](?P<s>{names})[\"']", re.I),
        re.compile(rf"search_path\s*(?:=|to)\s*[\"']?(?P<s>{names})\b", re.I),
    ]


def scan(root: Path, ownership: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for service, own in ownership.items():
        base = root / "services" / service
        if not base.exists():
            continue
        patterns = _patterns([s for s in ownership.values() if s != own])
        for f in sorted(base.rglob("*")):
            if f.suffix not in SUFFIXES or SKIP & set(f.relative_to(base).parts):
                continue
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                for p in patterns:
                    m = p.search(line)
                    # event type names such as procurement.order.confirmed.v1 are not table references
                    if m and not re.search(r"\.v[0-9]+$", re.match(r"[\w.]+", line[m.start("s"):])[0]):
                        problems.append(f"{f.relative_to(root)}:{n}: {service} references schema {m['s']!r} (owns {own!r})")
    return problems


MIGRATIONS_TEST = "infra/tests/test_migrations_postgres.py"


def run(root: Path, ownership: dict[str, str], database: bool = False, runner: Callable = subprocess.run,
        which: Callable = shutil.which) -> GateResult:
    """Static scan always; the PostgreSQL role-grant test only when `database` is on (T056): it needs Docker and takes about a minute."""
    started = utc_now()
    if not ownership:
        return GateResult("isolation", "not_run", ["schema_ownership is empty"], started)
    problems = scan(root, ownership)
    if problems:
        return GateResult("isolation", "fail", problems, started)
    static = ["no cross-schema references"]
    if not database:
        return GateResult("isolation", "pass", [*static, "role grants not checked (set MMI_GATES_DATABASE=1 to run the PostgreSQL test)"], started)
    cmd = suite_gate.Cmd((suite_gate.PY, "-m", "pytest", "-q", "-rf", MIGRATIONS_TEST), env=(("RUN_PG_MIGRATIONS", "1"),),
                         requires_paths=(MIGRATIONS_TEST,), requires_tools=("docker",))
    db = suite_gate.run_commands("isolation", [cmd], root, runner=runner, which=which)
    return GateResult("isolation", db.result, [*static, *db.evidence], started)
