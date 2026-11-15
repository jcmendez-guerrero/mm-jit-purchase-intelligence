"""T023: buyer-excluded anomaly days, applied as an overlay on the demand series (feature 012, FR-004, research R3).

An excluded day is reported as censored in the series export, so the forecast leaves it out of what it learns from.
The ERP-derived demand rows are never edited or deleted: removing the decision restores the day exactly.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from db.tables import anomaly_flags
from sqlalchemy import select
from sqlalchemy.engine import Connection


def excluded_days(conn: Connection) -> dict[int, set[date]]:
    out: dict[int, set[date]] = defaultdict(set)
    for r in conn.execute(select(anomaly_flags.c.variant_id, anomaly_flags.c.day).where(anomaly_flags.c.decision == "excluded")).all():
        out[r.variant_id].add(r.day)
    return out
