"""T111: what activating a dataset would change, computed without activating it.

Compares the candidate with the dataset that is active now (rows added, removed, changed) and shows the effect on the latest series:
which variants gain history, which become forecastable, which are skipped because the seed rows are too sparse. It does not re-run the
backtest; the run that follows an activation does, and records the dataset it used.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from db.tables import seed_rows
from runs.seeds import ActiveSeeds, apply_seeds
from sqlalchemy import select
from sqlalchemy.engine import Connection

from seeds.lifecycle import active_dataset


def _rows(conn: Connection, dataset_id: str) -> dict[tuple[int, Any, str], Decimal]:
    return {(r.variant_id, r.day, r.kind): Decimal(str(r.quantity)) for r in conn.execute(select(seed_rows).where(seed_rows.c.dataset_id == dataset_id)).all()}


def _by_variant(rows: dict[tuple[int, Any, str], Decimal], dataset_id: str) -> ActiveSeeds:
    s = ActiveSeeds(dataset_id, 0)
    for (v, d, _k), q in rows.items():
        s.by_variant.setdefault(v, {})[d] = s.by_variant.get(v, {}).get(d, Decimal(0)) + q
    return s


def dry_run(conn: Connection, dataset_id: str, series: list[dict[str, Any]], min_history: int) -> dict[str, Any]:
    cand = _rows(conn, dataset_id)
    cur = active_dataset(conn)
    base = _rows(conn, cur.id) if cur is not None and cur.id != dataset_id else {}
    added = [k for k in cand if k not in base]
    removed = [k for k in base if k not in cand]
    changed = [k for k in cand if k in base and base[k] != cand[k]]
    _out, cand_rep = apply_seeds(series, _by_variant(cand, dataset_id), min_history)
    base_rep = apply_seeds(series, _by_variant(base, cur.id if cur is not None else ""), min_history)[1] if base else None
    gained = sorted(cand_rep.used - (base_rep.used if base_rep else set()))
    lost = sorted((base_rep.used if base_rep else set()) - cand_rep.used)
    return {"dataset_id": dataset_id, "compared_with": None if cur is None or cur.id == dataset_id else cur.id,
            "rows": {"added": len(added), "removed": len(removed), "changed": len(changed), "unchanged": len(cand) - len(added) - len(changed)},
            "variants_gaining_history": gained[:200], "variants_losing_history": lost[:200], "skipped_sparse": sorted(cand_rep.skipped_sparse)[:200],
            "backtest": "not_run_until_activation"}
