"""Synthetic series for the data-quality and forecast-intelligence tests (feature 018). Synthetic data only.

Each case is a plain dict in the shape of inventory-service's series export (``variant_id``, ``start_day``, ``demand``,
``censored``, ``price``, ``segment``, ``service_level``), built from fixed arithmetic so every run is identical.
SKUs are fictional (``EJ-9101`` to ``EJ-9107``) and variant ids stay in a test-only range.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

START = date(2026, 1, 1)
DAYS = 120

# case name -> (sku, variant_id)
CASES: dict[str, tuple[str, int]] = {
    "smooth": ("EJ-9101", 910101),
    "intermittent": ("EJ-9102", 910102),
    "stockout": ("EJ-9103", 910103),
    "outlier": ("EJ-9104", 910104),
    "rejected": ("EJ-9105", 910105),
    "seed_only": ("EJ-9106", 910106),
    "short_history": ("EJ-9107", 910107),
}

STOCKOUT_DAYS = range(40, 56)   # 16 censored days with zero sales
OUTLIER_DAY = 70
OUTLIER_VALUE = 90

# Movements an ingestion step would refuse: (day offset, quantity text, reason code). Never counted as demand.
REJECTED_MOVEMENTS: dict[str, list[tuple[int, str, str]]] = {
    "rejected": [(5, "3", "malformed_date"), (12, "-2", "negative_quantity"), (20, "x", "malformed_quantity"), (33, "4", "ambiguous_sku"), (47, "1", "duplicate_movement")],
}

# Seed values for the seed-only product: provenance is always "estimated", never "observed".
SEED_ROWS: dict[str, list[tuple[int, int, str]]] = {"seed_only": [(d, 2, "estimated") for d in range(0, 60, 3)]}


def _smooth(n: int) -> list[int]:
    return [3 + (1 if d % 3 == 0 else 0) for d in range(n)]


def _intermittent(n: int) -> list[int]:
    return [1 + (d // 9) % 2 if d % 9 == 4 else 0 for d in range(n)]


def build_series(name: str) -> dict[str, Any]:
    sku, variant_id = CASES[name]
    n = DAYS
    if name == "smooth":
        demand = _smooth(n)
    elif name == "intermittent":
        demand = _intermittent(n)
    elif name == "stockout":
        demand = [0 if d in STOCKOUT_DAYS else v for d, v in enumerate(_smooth(n))]
    elif name == "outlier":
        demand = _smooth(n)
        demand[OUTLIER_DAY] = OUTLIER_VALUE
    elif name == "rejected":
        demand = _smooth(n)
    elif name == "seed_only":
        demand = [0] * 60 + _smooth(60)            # no ERP history for the first 60 days
    elif name == "short_history":
        n = 20
        demand = _smooth(n)
    else:
        raise KeyError(name)
    censored = [name == "stockout" and d in STOCKOUT_DAYS for d in range(len(demand))]
    return {"sku": sku, "variant_id": variant_id, "start_day": START.isoformat(), "demand": demand, "censored": censored,
            "price": "10.00", "service_level": "0.95", "segment": {"pattern": "intermittent" if name == "intermittent" else "smooth"}}


def build_all() -> dict[str, dict[str, Any]]:
    return {name: build_series(name) for name in CASES}


def through_day(series: dict[str, Any]) -> str:
    return (date.fromisoformat(series["start_day"]) + timedelta(days=len(series["demand"]) - 1)).isoformat()
