"""People and the browser use the SKU; the ERP variant id stays between services (project rule 5, feature 014 FR-008a).

A pure transport filter: it removes the key `variant_id` at any depth from a JSON value and does nothing else.
"""

from __future__ import annotations

from typing import Any


def without_variant_ids(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: without_variant_ids(v) for k, v in value.items() if k != "variant_id"}
    if isinstance(value, list):
        return [without_variant_ids(v) for v in value]
    return value
