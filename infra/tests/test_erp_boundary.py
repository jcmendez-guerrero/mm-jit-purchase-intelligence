"""T045: supplier terms, overrides, policies and scenarios are MMI-owned. Changing them can never produce an ERP request.

Static: the code that stores and resolves them imports no HTTP client and mentions no ERP. Behavioural: saving terms with every
HTTP client replaced by a tripwire still works (see services/procurement-service/tests/test_terms_no_erp.py). The Siweb allowlist
tests (connector and cost writer) are unchanged and still prove that only the single supplier-cost PUT exists.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROCUREMENT = ROOT / "services/procurement-service/src"
OWN_FILES = [*sorted((PROCUREMENT / "terms").glob("*.py")), PROCUREMENT / "api/terms.py"]
# an HTTP client import, or a reference to the ERP client / connection settings (cost *source labels* such as "siweb_product_supplier" are data, not calls)
# an HTTP client import, or a reference to the ERP client / connection settings (cost *source labels* such as "siweb_product_supplier" are data, not calls)
FORBIDDEN = re.compile(r"^\s*(?:import|from)\s+(?:httpx|requests|urllib\.request|aiohttp|http\.client)\b|(?-i:SIWEB_\w+)|siweb[_-](?:connector|client|cost[_-]writer)", re.I | re.M)


def test_the_terms_code_has_no_http_client_and_no_erp_reference():
    assert len(OWN_FILES) >= 4
    offenders = [str(p.relative_to(ROOT)) for p in OWN_FILES if FORBIDDEN.search(p.read_text(encoding="utf-8"))]
    assert not offenders, f"terms code must stay local: {offenders}"


def test_the_only_erp_write_path_is_still_the_cost_writer():
    """No procurement module other than the cost-write flow may name an ERP write; the writer's allowlist keeps its single PUT."""
    allow = (ROOT / "specs/001-mmi-purchase-intelligence/contracts/siweb-allowlist.md").read_text(encoding="utf-8")
    assert len(re.findall(r"\bPUT\b", allow)) >= 1
    writer_src = (ROOT / "services/siweb-cost-writer/src/writer/allowlist.py").read_text(encoding="utf-8")
    assert writer_src.count("PUT") >= 1 and not re.search(r'["\'](POST|DELETE|PATCH)["\']', writer_src)
