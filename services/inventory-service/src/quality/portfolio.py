"""T061: the catalogue-wide view of data quality and demand classes (feature 018, FR-019, SC-007).

``portfolio_aggregate`` holds one row per non-service product, rebuilt in one go (derived data, never edited). Every product is in it: one with
no class yet falls in ``sin_clasificar`` and one with no forecast result yet in the ``pending`` eligibility bucket, so every distribution adds up to
the number of active products. Filters (category A/B/C/critical, family, supplier) use the same ``variant_scope`` as the dashboard, so both agree.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from dashboard.kpis import Filters, variant_scope
from db.tables import data_quality_snapshot, portfolio_aggregate, product_segments, variants
from demand.provenance import SURROGATE_BASE
from sqlalchemy import delete, insert, select
from sqlalchemy.engine import Connection

ELIGIBILITY_KEYS = ("eligible", "manual_review_only", "not_eligible", "pending")
CONFIDENCE_KEYS = ("alta", "media", "baja", "none")
BUCKETS = ("class", "eligibility", "confidence")
ORIGINS = ("erp", "local_export")                                   # counts are never summed across origins (FR-014, FR-023)
UNCLASSIFIED = "sin_clasificar"
INTERMITTENT = frozenset({"intermittent", "lumpy"})
SIX = Decimal("0.000001")


def _share(part: int, whole: int) -> Decimal | None:
    return None if whole <= 0 else min(Decimal(part) / Decimal(whole), Decimal(1)).quantize(SIX)


def rebuild_portfolio(conn: Connection, eligibility: dict[str, tuple[str, str | None]] | None = None, run_id: str | None = None, now: datetime | None = None) -> int:
    """Replaces the aggregate. ``eligibility`` maps SKU to (eligibility, confidence) from the latest forecast run; None or a missing SKU is ``pending``."""
    now = now or datetime.now(UTC)
    segs = {r.variant_id: r for r in conn.execute(select(product_segments)).all()}
    snaps: dict[int, Any] = {}
    for r in conn.execute(select(data_quality_snapshot).order_by(data_quality_snapshot.c.built_at, data_quality_snapshot.c.id)).all():
        snaps[r.variant_id] = r                                          # the latest wins
    rows = []
    for v in conn.execute(select(variants.c.external_id, variants.c.sku).where(variants.c.is_service.is_(False))).all():
        seg, snap = segs.get(v.external_id), snaps.get(v.external_id)
        known = eligibility is not None and v.sku in eligibility
        elig, conf = eligibility[v.sku] if known and eligibility is not None else ("pending", None)
        rows.append({
            "variant_id": v.external_id, "origin": "local_export" if v.external_id >= SURROGATE_BASE else "erp",
            "abc": seg.abc if seg else "-", "xyz": seg.xyz if seg else "-", "pattern": seg.pattern if seg else "none", "intermittent": bool(seg and seg.pattern in INTERMITTENT),
            "coverage_ratio": snap.coverage_ratio if snap else None,
            "rejected_share": _share(snap.rejected_count + snap.quarantined_count, snap.days_with_data) if snap else None,
            "anomaly_share": _share(snap.anomaly_count, snap.days_in_period) if snap else None,
            "eligibility": elig, "confidence": conf, "received_run_id": run_id if known else None, "received_at": now if known else None,
            "category": None, "supplier": None})
    conn.execute(delete(portfolio_aggregate))
    if rows:
        conn.execute(insert(portfolio_aggregate), rows)
    return len(rows)


def _class_key(abc: str, xyz: str) -> str:
    return UNCLASSIFIED if abc == "-" else f"{abc}{xyz}"


def _in_scope(conn: Connection, f: Filters, origin: str = "erp") -> list[Any]:
    scope = variant_scope(conn, f)
    rows = conn.execute(select(portfolio_aggregate, variants.c.sku).join(variants, variants.c.external_id == portfolio_aggregate.c.variant_id)).all()
    return [r for r in rows if r.variant_id in scope and r.origin == origin]


def portfolio(conn: Connection, f: Filters, worst: int = 10, origin: str = "erp") -> dict[str, Any]:
    rows = _in_scope(conn, f, origin)
    by_class: dict[str, int] = {}
    by_elig = dict.fromkeys(ELIGIBILITY_KEYS, 0)
    by_conf = dict.fromkeys(CONFIDENCE_KEYS, 0)
    for r in rows:
        by_class[_class_key(r.abc, r.xyz)] = by_class.get(_class_key(r.abc, r.xyz), 0) + 1
        by_elig[r.eligibility] += 1
        by_conf[r.confidence or "none"] += 1

    def buckets(kind: str, counts: dict[str, int]) -> list[dict[str, Any]]:
        return [{"key": k, "count": n, "drilldown": f"bucket={kind}&key={k}"} for k, n in counts.items()]

    ranked = sorted((r for r in rows if r.coverage_ratio is not None), key=lambda r: (r.coverage_ratio, -((r.rejected_share or 0) + (r.anomaly_share or 0)), r.sku or ""))
    return {"filters": {"category": f.category, "supplier": f.supplier_id, "origin": origin}, "active_products": len(rows), "by_class": buckets("class", dict(sorted(by_class.items()))),
            "by_eligibility": buckets("eligibility", by_elig), "by_confidence": buckets("confidence", by_conf),
            "worst_quality": [{"sku": r.sku, "coverage_ratio": str(Decimal(r.coverage_ratio).quantize(SIX)), "rejected_share": None if r.rejected_share is None else str(Decimal(r.rejected_share).quantize(SIX)),
                               "anomaly_share": None if r.anomaly_share is None else str(Decimal(r.anomaly_share).quantize(SIX))} for r in ranked[:worst]]}


def bucket_products(conn: Connection, f: Filters, bucket: str, key: str, limit: int = 50, offset: int = 0, origin: str = "erp") -> dict[str, Any]:
    """The SKUs behind one count, in SKU order, paged. The same scope as ``portfolio``, so a count and its list always match."""
    if bucket == "class":
        pick = lambda r: _class_key(r.abc, r.xyz) == key  # noqa: E731
    elif bucket == "eligibility":
        pick = lambda r: r.eligibility == key  # noqa: E731
    else:
        pick = lambda r: (r.confidence or "none") == key  # noqa: E731
    skus = sorted(r.sku or "" for r in _in_scope(conn, f, origin) if pick(r))
    return {"bucket": bucket, "key": key, "total": len(skus), "skus": skus[offset:offset + limit]}
