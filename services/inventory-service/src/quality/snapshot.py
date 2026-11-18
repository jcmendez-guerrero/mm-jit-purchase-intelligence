"""T022: the per-product data-quality snapshot, anomaly flags and buyer decisions (feature 018, FR-002 to FR-006).

Everything here is derived from stored ERP data and never edits it. A snapshot is idempotent: the same inputs (coverage,
counts, flags and their decisions, configuration version) give the same input hash and reuse the stored row.
Quarantine terms: ``quarantined_count`` are open items, ``rejected_count`` are items a buyer chose to ignore, and
``ambiguous_count`` are those whose codes say the SKU or reference was ambiguous. Reasons are codes, never free text.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from audit import ANOMALY_DECIDED
from audit import append as audit
from classification.policy_source import current_config
from db.tables import (
    ALL_WAREHOUSES,
    anomaly_flags,
    data_quality_snapshot,
    demand_observations,
    review_decisions,
    stock_history,
    stock_movements,
)
from demand.provenance import SURROGATE_BASE
from demand.provider import DEMAND_REASONS
from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.engine import Connection

from quality.anomalies import detect
from quality.coverage import coverage

DECISIONS = ("accepted", "excluded")
REASON_CODES = ("data_error", "one_off_event", "stock_miscount", "other")
DEFAULT_DAYS = 90


class DecisionError(Exception):
    code = "quality_decision_invalid"


class NoFlagError(Exception):
    code = "quality_anomaly_not_found"


class _Data:
    """What the quality of a group of products is computed from, read with one statement per table instead of one per product."""

    def __init__(self, conn: Connection, ids: list[int], ignored: set[Any] | None = None) -> None:
        self.hist: dict[int, dict[date, bool]] = defaultdict(dict)
        self.sold: dict[int, Counter[date]] = defaultdict(Counter)
        self.flags: dict[int, list[tuple[date, str, str]]] = defaultdict(list)
        self.quarantined: dict[int, list[Any]] = defaultdict(list)
        self.movements: dict[int, list[Any]] = defaultdict(list)
        for r in conn.execute(select(stock_history.c.variant_id, stock_history.c.day, stock_history.c.censored)
                              .where(stock_history.c.variant_id.in_(ids), stock_history.c.warehouse_id == ALL_WAREHOUSES)):
            self.hist[r.variant_id][r.day] = bool(r.censored)
        for r in conn.execute(select(demand_observations.c.variant_id, demand_observations.c.day, demand_observations.c.demand_qty).where(demand_observations.c.variant_id.in_(ids))):
            self.sold[r.variant_id][r.day] += r.demand_qty
        for r in conn.execute(select(anomaly_flags.c.variant_id, anomaly_flags.c.day, anomaly_flags.c.rule_id, anomaly_flags.c.decision).where(anomaly_flags.c.variant_id.in_(ids))):
            self.flags[r.variant_id].append((r.day, r.rule_id, r.decision))
        for r in conn.execute(select(stock_movements.c.variant_id, stock_movements.c.external_id, stock_movements.c.quarantine_codes)
                              .where(stock_movements.c.variant_id.in_(ids), stock_movements.c.quarantined)):
            self.quarantined[r.variant_id].append(r)
        for r in conn.execute(select(stock_movements.c.variant_id, stock_movements.c.reason, stock_movements.c.created_at_utc)
                              .where(stock_movements.c.variant_id.in_(ids), ~stock_movements.c.quarantined, or_(stock_movements.c.reason.is_(None), stock_movements.c.reason.notin_(DEMAND_REASONS)))):
            self.movements[r.variant_id].append(r)
        self.ignored = ignored if ignored is not None else _ignored(conn)

    def series(self, variant_id: int) -> tuple[list[date], list[int], list[bool]]:
        hist = self.hist.get(variant_id)
        if not hist:
            return [], [], []
        sold = self.sold.get(variant_id, Counter())
        first, last = min(hist), max(hist)
        days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
        return days, [sold.get(d, 0) for d in days], [hist.get(d, False) for d in days]


def _ignored(conn: Connection) -> set[Any]:
    return set(conn.execute(select(review_decisions.c.external_id).where(review_decisions.c.decision == "ignore")).scalars())


def _new_flags(variant_id: int, data: _Data) -> list[Any]:
    """The anomalies detected now that have no flag yet; existing flags and their decisions are left alone."""
    have = {(day, rule) for day, rule, _ in data.flags.get(variant_id, [])}
    days, demand, censored = data.series(variant_id)
    return [a for a in detect(days, demand, censored) if (a.day, a.rule_id) not in have]


def _flag_rows(variant_id: int, new: list[Any], now: datetime) -> list[dict[str, Any]]:
    return [{"variant_id": variant_id, "day": a.day, "rule_id": a.rule_id, "original_value": Decimal(a.original_value), "decision": "pending", "created_at": now} for a in new]


def refresh_flags(conn: Connection, variant_id: int, now: datetime | None = None) -> int:
    """Inserts flags for newly detected anomalies; existing flags and their decisions are left alone. Returns the new count."""
    now = now or datetime.now(UTC)
    new = _new_flags(variant_id, _Data(conn, [variant_id]))
    if new:
        conn.execute(insert(anomaly_flags), _flag_rows(variant_id, new, now))
    return len(new)


def _utc(moment: datetime) -> str:
    """A stored moment as ISO text that always says UTC (SQLite hands back naive values, PostgreSQL aware ones)."""
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC).isoformat()


def _plain(value: Any) -> str:
    """A stored decimal as plain text: '90' for a whole number, '2.5' otherwise (never scientific notation)."""
    d = Decimal(value)
    return str(int(d)) if d == d.to_integral_value() else format(d.normalize(), "f")


def list_flags(conn: Connection, variant_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(select(anomaly_flags).where(anomaly_flags.c.variant_id == variant_id).order_by(anomaly_flags.c.day, anomaly_flags.c.rule_id)).all()
    return [{"day": r.day.isoformat(), "rule_id": r.rule_id, "original_value": _plain(r.original_value),
             "decision": r.decision, "decided_by": r.decided_by, "decided_at": _utc(r.decided_at) if r.decided_at else None, "reason_code": r.reason_code} for r in rows]


def needs_second_factor(conn: Connection, variant_id: int, day: date, decision: str) -> bool:
    """Excluding a day, and reversing an exclusion (accepting a day that was excluded), are the changes that need a recent second-factor check (FR-004)."""
    if decision == "excluded":
        return True
    return conn.execute(select(anomaly_flags.c.id).where(anomaly_flags.c.variant_id == variant_id, anomaly_flags.c.day == day, anomaly_flags.c.decision == "excluded").limit(1)).first() is not None


def decide(conn: Connection, variant_id: int, day: date, decision: str, reason_code: str | None, actor: str, now: datetime | None = None) -> bool:
    """Sets the decision on every flag of that day. Returns False when nothing changed (idempotent), True otherwise."""
    if decision not in DECISIONS or (reason_code is not None and reason_code not in REASON_CODES):
        raise DecisionError(decision)
    rows = conn.execute(select(anomaly_flags).where(anomaly_flags.c.variant_id == variant_id, anomaly_flags.c.day == day)).all()
    if not rows:
        raise NoFlagError(str(day))
    pending = [r for r in rows if r.decision != decision or r.reason_code != reason_code]
    if not pending:
        return False
    now = now or datetime.now(UTC)
    before = sorted({r.decision for r in rows})
    for r in pending:
        conn.execute(update(anomaly_flags).where(anomaly_flags.c.id == r.id).values(decision=decision, decided_by=actor, decided_at=now, reason_code=reason_code))
    audit(conn, actor, ANOMALY_DECIDED, "anomaly_flags", f"{variant_id}:{day.isoformat()}", before={"decision": before},
          after={"decision": decision, "reason_code": reason_code, "config": current_config()[1]}, now=now)
    return True


def default_period(conn: Connection, variant_id: int, days: int = DEFAULT_DAYS) -> tuple[date, date]:
    last = conn.execute(select(func.max(stock_history.c.day)).where(stock_history.c.variant_id == variant_id)).scalar() or datetime.now(UTC).date()
    return last - timedelta(days=days - 1), last


def _assemble(variant_id: int, start: date, end: date, config_id: str, data: _Data, new: list[Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """The snapshot of one product over one period, from data already read: its key (what makes it idempotent) and its values. Pure."""
    in_period = {d: c for d, c in data.hist.get(variant_id, {}).items() if start <= d <= end}
    sold = {d for d in data.sold.get(variant_id, {}) if start <= d <= end}
    cov = coverage(set(in_period) | sold, start, end)
    censored_days = sum(in_period.values())
    reasons: Counter[str] = Counter()
    rejected = open_items = ambiguous = 0
    for m in data.quarantined.get(variant_id, []):
        codes = [c for c in (m.quarantine_codes or "").split(",") if c]
        reasons.update(codes)
        ambiguous += any("ambiguous" in c for c in codes)
        if m.external_id in data.ignored:
            rejected += 1
        else:
            open_items += 1
    excluded_types: Counter[str] = Counter()
    for m in data.movements.get(variant_id, []):
        if m.reason not in DEMAND_REASONS and m.created_at_utc is not None and start <= m.created_at_utc.date() <= end:
            excluded_types[m.reason] += 1
    flags = [f for f in data.flags.get(variant_id, []) if start <= f[0] <= end] + [(a.day, a.rule_id, "pending") for a in new if start <= a.day <= end]
    anomaly_count = len({day for day, _rule, decision in flags if decision != "accepted"})
    digest = hashlib.sha256(json.dumps({"cov": [cov.days_in_period, cov.days_with_data, [(a.isoformat(), b.isoformat()) for a, b in cov.gaps]], "q": [open_items, rejected, ambiguous, sorted(reasons.items())],
                                         "x": sorted(excluded_types.items()), "a": sorted((day.isoformat(), rule, decision) for day, rule, decision in flags), "c": censored_days, "cfg": config_id},
                                        sort_keys=True).encode()).hexdigest()
    key = {"variant_id": variant_id, "period_start": start, "period_end": end, "config_version_id": config_id, "input_hash": digest}
    values = {"days_in_period": cov.days_in_period, "days_with_data": cov.days_with_data, "coverage_ratio": cov.ratio,
              "gap_days": [{"from": a.isoformat(), "to": b.isoformat()} for a, b in cov.gaps], "rejected_count": rejected, "quarantined_count": open_items,
              "ambiguous_count": ambiguous, "reason_counts": dict(reasons), "excluded_by_type": dict(excluded_types), "anomaly_count": anomaly_count,
              "censored_days": censored_days, "origin": "local_export" if variant_id >= SURROGATE_BASE else "erp", "dataset_version_id": None}
    return key, values


def build_snapshot(conn: Connection, variant_id: int, start: date, end: date, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    data = _Data(conn, [variant_id])
    new = _new_flags(variant_id, data)
    if new:
        conn.execute(insert(anomaly_flags), _flag_rows(variant_id, new, now))
    key, values = _assemble(variant_id, start, end, current_config()[1], data, new)
    stored = conn.execute(select(data_quality_snapshot).where(*[data_quality_snapshot.c[k] == v for k, v in key.items()])).first()
    if stored is None:
        conn.execute(insert(data_quality_snapshot).values(**key, **values, built_at=now))
        stored = conn.execute(select(data_quality_snapshot).where(*[data_quality_snapshot.c[k] == v for k, v in key.items()])).first()
    if stored is None:
        raise RuntimeError("the snapshot row is missing right after it was stored")
    return {"period_start": start.isoformat(), "period_end": end.isoformat(), "days_in_period": stored.days_in_period, "days_with_data": stored.days_with_data,
            "coverage_ratio": str(Decimal(stored.coverage_ratio).quantize(Decimal("0.000001"))), "gap_days": stored.gap_days, "rejected_count": stored.rejected_count,
            "quarantined_count": stored.quarantined_count, "ambiguous_count": stored.ambiguous_count,
            "reason_counts": [{"key": k, "count": v} for k, v in sorted(stored.reason_counts.items())],
            "excluded_by_type": [{"key": k, "count": v} for k, v in sorted(stored.excluded_by_type.items())], "anomaly_count": stored.anomaly_count,
            "censored_days": stored.censored_days, "origin": stored.origin, "config_version_id": stored.config_version_id, "dataset_version_id": stored.dataset_version_id,
            "built_at": _utc(stored.built_at)}


CHUNK = 500        # products read and written together; keeps memory bounded and the statements per product close to zero


def rebuild_snapshots(conn: Connection, variant_ids: list[int], now: datetime | None = None) -> int:
    """Flags and the default-period snapshot for every given product, in blocks: a fixed handful of statements per block, never one set per product.

    Stores exactly what ``build_snapshot`` stores (same code); a snapshot whose inputs did not change is not added again. Returns the number of products done.
    """
    now = now or datetime.now(UTC)
    config_id = current_config()[1]
    ignored = _ignored(conn)
    for i in range(0, len(variant_ids), CHUNK):
        ids = variant_ids[i:i + CHUNK]
        data = _Data(conn, ids, ignored)
        last = {r.variant_id: r.last for r in conn.execute(select(stock_history.c.variant_id, func.max(stock_history.c.day).label("last"))
                                                           .where(stock_history.c.variant_id.in_(ids)).group_by(stock_history.c.variant_id))}
        flag_rows: list[dict[str, Any]] = []
        built: list[dict[str, Any]] = []
        for vid in ids:
            end = last.get(vid) or now.date()
            new = _new_flags(vid, data)
            flag_rows += _flag_rows(vid, new, now)
            key, values = _assemble(vid, end - timedelta(days=DEFAULT_DAYS - 1), end, config_id, data, new)
            built.append({**key, **values, "built_at": now})
        if flag_rows:
            conn.execute(insert(anomaly_flags), flag_rows)
        have = {(r.variant_id, r.period_start, r.period_end, r.input_hash) for r in conn.execute(
            select(data_quality_snapshot.c.variant_id, data_quality_snapshot.c.period_start, data_quality_snapshot.c.period_end, data_quality_snapshot.c.input_hash)
            .where(data_quality_snapshot.c.variant_id.in_(ids), data_quality_snapshot.c.config_version_id == config_id))}
        fresh = [r for r in built if (r["variant_id"], r["period_start"], r["period_end"], r["input_hash"]) not in have]
        if fresh:
            conn.execute(insert(data_quality_snapshot), fresh)
    return len(variant_ids)
