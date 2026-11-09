# ruff: noqa: F811
"""T048 (SC-011, FR-032): saving and reading a supplier's terms stays under 300 ms at the 95th percentile with 50 versions in the history.

Measured through the HTTP route on the in-memory test database, so it covers validation, the append, the history read and the audit entry,
not the network. Production adds only a database round trip.
"""

import statistics
import time

from refusal_support import app, client, engine, h, sid  # noqa: F401
from test_terms_api import BODY

VERSIONS = 50
BUDGET_MS = 300.0


def p95(samples: list[float]) -> float:
    return statistics.quantiles(samples, n=20)[-1]


def test_terms_save_and_read_stay_under_the_budget_with_fifty_versions(client, sid):
    saves = []
    for i in range(VERSIONS):
        headers = h(**({"If-Match": f'"{i}"'} if i else {}))
        start = time.perf_counter()
        res = client.put(f"/suppliers/{sid}/terms", json={**BODY, "lead_time_days": 1 + i % 20, "reason": f"cambio {i}"}, headers=headers)
        saves.append((time.perf_counter() - start) * 1000)
        assert res.status_code == 200, res.text
    reads = []
    for _ in range(40):
        start = time.perf_counter()
        res = client.get(f"/suppliers/{sid}/terms", headers=h("viewer"))
        reads.append((time.perf_counter() - start) * 1000)
        assert res.status_code == 200 and len(res.json()["history"]) == VERSIONS
    assert p95(saves) < BUDGET_MS, f"save p95 {p95(saves):.1f} ms"
    assert p95(reads) < BUDGET_MS, f"read p95 {p95(reads):.1f} ms"
