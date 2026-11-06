"""T015: error codes are stable snake_case, documented, and every one has an es-ES message (FR-035)."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODES = json.loads((ROOT / "packages/contracts/errors/error_codes.json").read_text(encoding="utf-8"))["codes"]
WEB = json.loads((ROOT / "apps/web/src/i18n/es-ES.json").read_text(encoding="utf-8"))
DOC = (ROOT / "specs/002-mmi-operational-console/contracts/error-keys.md").read_text(encoding="utf-8")
SNAKE = re.compile(r"[a-z][a-z0-9_]*")


def test_codes_are_snake_case_with_a_valid_http_status():
    assert CODES
    for code, spec in CODES.items():
        assert SNAKE.fullmatch(code), code
        assert 200 <= spec["http"] <= 599
        assert spec["kind"] in {"request", "row", "flag"}


def test_every_code_has_a_spanish_message():
    missing = [c for c in CODES if not WEB.get(f"errors.{c}")]
    assert not missing, f"no es-ES message for: {missing}"


def test_web_has_no_orphan_error_messages():
    orphans = [k for k in WEB if k.startswith("errors.") and k.removeprefix("errors.") not in CODES]
    assert not orphans, f"messages without a code: {orphans}"


def test_documentation_table_matches_the_json():
    documented = set(re.findall(r"^\| ([a-z][a-z0-9_]+) \| \d{3}", DOC, re.M))
    assert documented == set(CODES)


def test_messages_are_spanish_sentences():
    for code in CODES:
        msg = WEB[f"errors.{code}"]
        assert msg[0].isupper() and msg.rstrip().endswith("."), code
        assert not re.search(r"\b(the|cannot|must|not allowed)\b", msg, re.I), f"English text in {code}"
