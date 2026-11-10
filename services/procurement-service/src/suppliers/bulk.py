"""T049: bulk assignment of products to a supplier (FR-035): preview first, then apply the latest preview (at most 15 minutes old)."""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from audit.chain import append as audit
from costs.recargo import RecargoTable
from costs.rules import CostRules
from costs.store import current
from db.tables import link_assignment_batches, product_refs, suppliers
from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.engine import Connection, Row
from terms.overrides import current_override

from suppliers.dedupe import name_key
from suppliers.links import LinkError, LinkInput, put_link
from suppliers.service import SupplierError, get_supplier

PREVIEW_TTL = timedelta(minutes=15)
MAX_MATCHES = 5000
MAX_SKUS = 5000


class BulkError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _clean_criteria(criteria: dict[str, Any]) -> dict[str, Any]:
    skus, q = criteria.get("skus"), criteria.get("q")
    if (skus is None) == (q is None):
        raise BulkError("bulk_criteria_invalid")
    if skus is not None:
        seen: dict[str, str] = {}
        for s in skus:
            if isinstance(s, str) and s.strip():
                seen.setdefault(s.strip().lower(), s.strip())
        if not seen or len(seen) > MAX_SKUS:
            raise BulkError("bulk_criteria_invalid")
        return {"skus": list(seen.values())}
    if not isinstance(q, str) or len(q.strip()) < 2:
        raise BulkError("bulk_criteria_invalid")
    return {"q": q.strip()}


def _match(conn: Connection, criteria: dict[str, Any]) -> tuple[list[Row[Any]], list[str]]:
    if "skus" in criteria:
        refs, unknown = [], []
        for s in criteria["skus"]:
            r = conn.execute(select(product_refs).where(func.lower(product_refs.c.sku) == s.lower()).order_by(product_refs.c.variant_id).limit(1)).first()
            (refs.append(r) if r is not None else unknown.append(s))
        return refs, unknown
    like = f"%{criteria['q'].lower()}%"
    rows = conn.execute(select(product_refs).where(or_(func.lower(product_refs.c.sku).like(like), func.lower(product_refs.c.name).like(like)))
                        .order_by(product_refs.c.sku).limit(MAX_MATCHES + 1)).all()
    if len(rows) > MAX_MATCHES:
        raise BulkError("bulk_criteria_invalid", "too broad")
    seen: set[int] = set()
    return [r for r in rows if not (r.product_id in seen or seen.add(r.product_id))], []


def _classify(conn: Connection, supplier_id: str, refs: list[Row[Any]], now: datetime) -> tuple[list[Row[Any]], list[Row[Any]], list[Row[Any]]]:
    existing, new, conflicts = [], [], []
    for r in refs:
        if current(conn, int(r.product_id), supplier_id, None) is not None:
            existing.append(r)
            continue
        new.append(r)
        others = conn.execute(select(suppliers.c.id).where(suppliers.c.id != supplier_id, suppliers.c.status == "active")).scalars().all()
        for other in others:
            o = current_override(conn, int(r.variant_id), other, now)
            if o is not None and o.preferred:
                conflicts.append(r)
                break
    return existing, new, conflicts


def preview_batch(conn: Connection, supplier_id: str, criteria: dict[str, Any], actor: str, *, now: datetime | None = None) -> dict[str, Any]:
    supplier = get_supplier(conn, supplier_id)
    if supplier.status != "active":
        raise SupplierError("supplier_deactivated")
    now = now or datetime.now(UTC)
    clean = _clean_criteria(criteria)
    refs, unknown = _match(conn, clean)
    existing, new, conflicts = _classify(conn, supplier_id, refs, now)
    bid = str(uuid.uuid4())
    latest = conn.execute(select(func.max(link_assignment_batches.c.created_at)).where(link_assignment_batches.c.supplier_id == supplier_id)).scalar()
    if latest is not None and now <= _aware(latest):
        now = _aware(latest) + timedelta(microseconds=1)       # previews of one supplier are strictly ordered: only the newest can be applied
    conn.execute(insert(link_assignment_batches).values(id=bid, created_by=actor, created_at=now, criteria=clean, supplier_id=supplier_id,
                                                        products_matched=len(refs), products_changed=0, conflicts=len(conflicts), status="previewed"))
    return {"batch_id": bid, "matched": len(refs), "new": len(new), "existing": len(existing), "conflicts": len(conflicts),
            "conflict_skus": [r.sku for r in conflicts], "unknown": unknown, "expires_at": (now + PREVIEW_TTL).isoformat()}


def apply_batch(conn: Connection, batch_id: str, actor: str, rules: CostRules, table: RecargoTable, *, now: datetime | None = None,
                skip_conflicts: bool = False, refresh: Callable[[], None] | None = None) -> dict[str, Any]:
    """Applies a previewed batch. Besides the totals the result lists what happened to each matched product (FR-018): linked, already_linked,
    conflict_skipped or no_cost, in SKU order."""
    now = now or datetime.now(UTC)
    batch = conn.execute(select(link_assignment_batches).where(link_assignment_batches.c.id == batch_id)).first()
    if batch is None:
        raise BulkError("bulk_preview_stale")
    newest = conn.execute(select(link_assignment_batches.c.id).where(link_assignment_batches.c.supplier_id == batch.supplier_id)
                          .order_by(link_assignment_batches.c.created_at.desc(), link_assignment_batches.c.id.desc()).limit(1)).scalar()
    if batch.status != "previewed" or now - _aware(batch.created_at) > PREVIEW_TTL or newest != batch.id:
        raise BulkError("bulk_preview_stale")
    refs, _ = _match(conn, dict(batch.criteria))
    existing, new, conflicts = _classify(conn, batch.supplier_id, refs, now)
    if conflicts and not skip_conflicts:
        raise BulkError("bulk_conflicts_unresolved")
    skip = {r.product_id for r in conflicts}
    changed = no_cost = 0
    outcome: dict[str, str] = {r.sku: "already_linked" for r in existing}
    for r in new:
        if r.product_id in skip:
            outcome[r.sku] = "conflict_skipped"
            continue
        try:
            put_link(conn, batch.supplier_id, r.sku, LinkInput(source="inventory_export"), actor, rules, table, now=now, refresh=refresh)
        except LinkError as exc:
            if exc.code in ("link_cost_invalid", "vat_unknown"):
                no_cost += 1
                outcome[r.sku] = "no_cost"
                continue
            raise
        changed += 1
        outcome[r.sku] = "linked"
        audit(conn, actor, "supplier.link_bulk", "supplier_link", f"{batch.supplier_id}:{r.sku}"[:60], after={"batch": batch.id}, now=now)
    conn.execute(update(link_assignment_batches).where(link_assignment_batches.c.id == batch.id).values(status="applied", applied_at=now, products_changed=changed))
    return {"changed": changed, "skipped_conflicts": len(skip) if conflicts else 0, "no_cost": no_cost,
            "rows": [{"sku": sku, "outcome": outcome[sku]} for sku in sorted(outcome)]}


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise BulkError("bulk_file_invalid")


def parse_assignment_file(conn: Connection, data: bytes) -> dict[str, Any]:
    """Two columns, SKU and supplier name. Names match a supplier only when exactly one active supplier has that name once folded."""
    text = _decode(data)
    first = text.split("\n", 1)[0]
    delim = max((",", ";", "\t"), key=lambda d: first.count(d))
    rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delim))
    if not rows:
        raise BulkError("bulk_file_invalid")
    head = [h.strip().lower() for h in rows[0]]
    try:
        i_sku = head.index("sku")
        i_sup = next(i for i, h in enumerate(head) if h in ("proveedor", "supplier"))
    except (ValueError, StopIteration) as exc:
        raise BulkError("bulk_file_invalid") from exc
    index: dict[str, list[str]] = {}
    for s in conn.execute(select(suppliers.c.id, suppliers.c.name, suppliers.c.status, suppliers.c.merged_into)).all():
        if s.status == "active" and s.merged_into is None:
            index.setdefault(name_key(s.name), []).append(s.id)
    groups: dict[str, list[str]] = {}
    errors: list[dict[str, Any]] = []
    for n, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        sku = (r[i_sku] if i_sku < len(r) else "").strip()
        name = (r[i_sup] if i_sup < len(r) else "").strip()
        if not sku:
            errors.append({"row": n, "code": "missing_sku"})
            continue
        ids = index.get(name_key(name), []) if name else []
        if len(ids) == 1:
            bucket = groups.setdefault(ids[0], [])
            if sku not in bucket:
                bucket.append(sku)
        else:
            errors.append({"row": n, "code": "link_ambiguous" if len(ids) > 1 else "link_no_match"})
    return {"groups": groups, "errors": errors, "rows": len(rows) - 1}
