"""T113: use the active seed dataset where ERP history is too short, never where actual history is enough.

Rules (FR-020..022): actual ERP demand always prevails on any day it covers; seed rows only extend the history backwards for a variant
whose actual history is shorter than ``min_history``, and only when the seed rows are dense enough to describe demand honestly (at least
half of the days in their span). A variant rescued this way is flagged ``seed_used``. Seeds are never written to ERP-derived tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from db.tables import seed_rows
from seeds.lifecycle import active_dataset
from sqlalchemy import select
from sqlalchemy.engine import Connection

MIN_DENSITY = Decimal("0.5")
RESCUABLE = {"new"}                  # the only ineligibility a longer history can cure


@dataclass
class ActiveSeeds:
    dataset_id: str
    version: int
    by_variant: dict[int, dict[date, Decimal]] = field(default_factory=dict)


@dataclass
class SeedReport:
    used: set[int] = field(default_factory=set)
    skipped_sparse: set[int] = field(default_factory=set)
    overlap_variants: int = 0          # variants with seed rows on days that already have actual ERP demand (the actuals prevail)
    overlap_days: int = 0              # how many such seed days there are in total


def load_active(conn: Connection) -> ActiveSeeds | None:
    ds = active_dataset(conn)
    if ds is None:
        return None
    out = ActiveSeeds(ds.id, ds.version)
    for r in conn.execute(select(seed_rows).where(seed_rows.c.dataset_id == ds.id)).all():
        out.by_variant.setdefault(r.variant_id, {})[r.day] = out.by_variant.get(r.variant_id, {}).get(r.day, Decimal(0)) + Decimal(str(r.quantity))
    return out


def apply_seeds(series: list[dict[str, Any]], seeds: ActiveSeeds, min_history: int) -> tuple[list[dict[str, Any]], SeedReport]:
    report = SeedReport()
    out: list[dict[str, Any]] = []
    for s in series:
        rows = seeds.by_variant.get(int(s["variant_id"]))
        if rows and s["demand"]:
            first_actual = date.fromisoformat(s["start_day"])
            last_actual = first_actual + timedelta(days=len(s["demand"]) - 1)
            on_actuals = sum(1 for d in rows if first_actual <= d <= last_actual)
            if on_actuals:
                report.overlap_variants += 1
                report.overlap_days += on_actuals
        if not rows or len(s["demand"]) >= min_history:
            out.append(s)                                              # enough actual history: seeds are not consulted
            continue
        start = date.fromisoformat(s["start_day"])
        earlier = {d: q for d, q in rows.items() if d < start}          # actuals prevail on every day they cover
        if not earlier:
            out.append(s)
            continue
        first = min(earlier)
        span = (start - first).days
        if Decimal(len(earlier)) / Decimal(span) < MIN_DENSITY:
            report.skipped_sparse.add(int(s["variant_id"]))
            out.append(s)
            continue
        prefix = [int(earlier.get(first + timedelta(days=i), Decimal(0)).quantize(Decimal(1), rounding=ROUND_HALF_UP)) for i in range(span)]
        seg = dict(s.get("segment") or {})
        if seg and not seg.get("forecast_eligible") and set(seg.get("reasons") or ()) <= RESCUABLE and len(prefix) + len(s["demand"]) >= min_history:
            seg["forecast_eligible"], seg["reasons"] = True, []
        elif seg and not seg.get("forecast_eligible"):
            out.append(s)                                              # still not forecastable for another reason: leave it alone
            continue
        report.used.add(int(s["variant_id"]))
        out.append({**s, "start_day": first.isoformat(), "demand": prefix + list(s["demand"]), "censored": [False] * len(prefix) + list(s["censored"]), "segment": seg or s.get("segment")})
    return out, report
