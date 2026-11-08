"""Tests use only the synthetic export fixtures; they never touch the owner's private folder."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "exports"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES
