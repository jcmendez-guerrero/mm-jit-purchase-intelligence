"""T156: the abuse suite. One place that names every abuse class, checks its tests exist, and runs them service by service.

Each service's tests need that service's own import path, so they run in their own process, exactly as in CI.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# abuse class -> (service, test files). A missing file fails the suite: a class cannot be dropped silently.
CLASSES = {
    "upload abuse (size, type, signature, decompression, macros, formulas)": ("forecast-service", ["tests/test_upload_hardening.py", "tests/test_seed_parsing.py"]),
    "upload abuse at the console edge (size, type, CSRF, role)": ("api-bff", ["tests/test_upload_security.py"]),
    "CSRF, anonymous access, viewer access and stale multi-factor on every mutating route": ("api-bff", ["tests/test_abuse_matrix.py"]),
    "role bypass and refusal audit": ("api-bff", ["tests/test_rbac_refusals.py", "tests/test_policies_rbac.py", "tests/test_suppliers_rbac.py"]),
    "separation of duties and fresh multi-factor on approval and cost release": ("procurement-service", ["tests/test_approval.py", "tests/test_approval_eligibility.py", "tests/test_margin_override.py"]),
    "object references on datasets and path traversal": ("forecast-service", ["tests/test_abuse_ids.py"]),
    "object references on scenarios": ("procurement-service", ["tests/test_abuse_ids.py"]),
    "formula injection in exports": ("forecast-service", ["tests/test_formula_safe_export.py"]),
    "formula injection in scenario and proposal exports": ("procurement-service", ["tests/test_scenarios_export.py"]),
    "admin-only re-runs": ("api-bff", ["tests/test_admin_rerun.py"]),
}


@pytest.mark.parametrize("name", sorted(CLASSES))
def test_every_abuse_class_has_tests(name):
    service, files = CLASSES[name]
    for f in files:
        path = ROOT / "services" / service / f
        assert path.is_file(), f"{name}: missing {service}/{f}"
        assert "def test_" in path.read_text(), f"{name}: {service}/{f} has no tests"


def test_the_abuse_tests_pass():
    failures = []
    by_service: dict[str, list[str]] = {}
    for service, files in CLASSES.values():
        by_service.setdefault(service, []).extend(f for f in files if f not in by_service.get(service, []))
    for service, files in by_service.items():
        res = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *files], cwd=ROOT / "services" / service, capture_output=True, text=True, timeout=300)
        if res.returncode != 0:
            failures.append(f"{service}:\n{res.stdout[-1500:]}")
    assert not failures, "\n".join(failures)
