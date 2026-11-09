"""Synthetic helpers for the gate tests: a throwaway repository root, never real data (T003)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))

SPEC_CONTRACTS = "specs/005-architecture-contracts-integration/contracts"
SCHEMAS = "docs/architecture/integration/schemas"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A minimal repo root holding copies of the real schemas and no artifacts."""
    shutil.copytree(REPO / SCHEMAS, tmp_path / SCHEMAS)
    shutil.copytree(REPO / SPEC_CONTRACTS, tmp_path / SPEC_CONTRACTS)
    return tmp_path


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()  # noqa: S603, S607


@pytest.fixture
def valid_artifacts(root: Path) -> Path:
    base = root / "docs/architecture/integration"
    (root / "services").mkdir(exist_ok=True)
    (root / "services/a.py").write_text("x = 1\n")
    write_json(base / "feature-status.json", {
        "audited_commit": "abc1234", "audited_at": "2026-11-08T00:00:00Z",
        "features": [{"id": "demo", "title": "Demo", "status": "partial", "evidence": ["services/a.py:1"], "owner": "agent-01"}],
    })
    write_json(base / "contract-matrix.json", {
        "matrix_version": 1, "generated_at": "2026-11-08T00:00:00Z", "schema_ownership": {"svc": "own"},
        "entries": [{"name": "money", "kind": "dto", "version": 1, "schema_path": "dto/money.v1.schema.json",
                     "owner": "svc", "consumers": [], "status": "frozen"}],
    })
    write_json(base / "integration-plan.json", {
        "base": "main",
        "steps": [{"pr": 1, "agent": "agent-01", "owned_paths": ["a/**"], "depends_on": [], "verification": ["contracts"], "state": "pending"}],
    })
    return root
