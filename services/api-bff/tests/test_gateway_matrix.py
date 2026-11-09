"""T055 (FR-005): the gateway's real endpoints equal the `endpoint` entries of the contract matrix.

Fails when an endpoint is added or removed without updating docs/architecture/integration/contract-matrix.json.
Refresh it with: python -m gates matrix --openapi <exported openapi.json> (see docs/architecture/integration/README.md).
"""

import json
from pathlib import Path

MATRIX = Path(__file__).resolve().parents[3] / "docs/architecture/integration/contract-matrix.json"
HTTP = ("get", "post", "put", "patch", "delete")


def test_gateway_endpoints_match_the_contract_matrix():
    from main import app

    live = {f"{method.upper()} {path}" for path, ops in app.openapi()["paths"].items() for method in ops if method in HTTP}
    listed = {e["name"] for e in json.loads(MATRIX.read_text())["entries"] if e["kind"] == "endpoint"}
    assert live - listed == set(), f"gateway endpoints missing from the matrix: {sorted(live - listed)}"
    assert listed - live == set(), f"matrix endpoints no longer in the gateway: {sorted(listed - live)}"
