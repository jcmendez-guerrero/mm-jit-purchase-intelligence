"""Feature 014 (T012, FR-003): the dashboard indicator contracts stay as PR 19 delivered them.

Changing either schema must go through Agent 00 and a deliberate update of these pins, never as a side effect of the completion work.
"""

import hashlib
from pathlib import Path

DTO = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "dto"

PINS = {
    "dashboard_indicators.v2.schema.json": "c9653dd84de635d4004c0633f122330882ae903bc76e22aa728ed7a47dfc75df",
    "dashboard_summary.v1.schema.json": "972276da1a7b5971808c72a17411db31cbc129b8c03d6105134b1d2010bf44d2",
}


def test_the_v1_and_v2_dashboard_schemas_are_byte_for_byte_unchanged():
    for name, expected in PINS.items():
        assert hashlib.sha256((DTO / name).read_bytes()).hexdigest() == expected, name
