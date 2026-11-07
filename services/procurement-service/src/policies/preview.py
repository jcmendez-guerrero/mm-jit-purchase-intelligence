"""T074: what a policy change would do, computed without saving it.

The candidate is saved inside a savepoint, the proposal inputs are rebuilt and solved, and the savepoint is rolled back, so the
audit chain and the policy tables are exactly as before. Only variant lines whose quantity changes are reported, with the spend change.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from proposals.generate import generate
from proposals.inputs import InputsProvider
from sqlalchemy.engine import Connection

from policies.service import PolicyValues, save_policy

PREVIEW_SECONDS = 10.0


def _solve(conn: Connection, provider: InputsProvider, today: date) -> tuple[dict[int, int], Decimal]:
    draft = generate(provider.build(conn, today), PREVIEW_SECONDS)
    return {ln.variant_id: ln.qty for ln in draft.lines}, draft.optimized_total


def preview_policy(conn: Connection, provider: InputsProvider, scope: str, key: str, values: PolicyValues, actor: str, today: date,
                   valid_from: date | None = None, run_date: date | None = None) -> dict[str, Any]:
    """``run_date`` is the date the comparison is made for (default: the policy start), so a future-dated policy is previewed as it will apply."""
    start = valid_from or today
    day = run_date or start
    before_lines, before_total = _solve(conn, provider, day)
    sp = conn.begin_nested()
    try:
        save_policy(conn, scope, key, values, actor, valid_from=start, today=today)
        after_lines, after_total = _solve(conn, provider, day)
    finally:
        sp.rollback()
    ids = sorted(set(before_lines) | set(after_lines))
    changed = [{"variant_id": v, "qty_before": before_lines.get(v, 0), "qty_after": after_lines.get(v, 0)} for v in ids if before_lines.get(v, 0) != after_lines.get(v, 0)]
    return {"as_of": day.isoformat(), "affected_count": len(changed), "affected": changed[:200], "spend_before": str(before_total), "spend_after": str(after_total),
            "spend_delta": str(after_total - before_total), "saved": False}
