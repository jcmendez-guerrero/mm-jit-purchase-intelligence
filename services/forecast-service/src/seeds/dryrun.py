"""T111: what activating a dataset would change, computed without activating it.

Compares the candidate with the dataset that is active now (rows added, removed, changed) and shows the effect on the latest series:
which variants gain history, which become forecastable, which are skipped because the seed rows are too sparse. It also runs the same
backtest the forecast run uses, once with the candidate and once with the current basis (the active dataset, or real demand only), and
reports the simulated cost of each so the buyer sees the effect before activating. Nothing is stored; the run that follows an activation
records the dataset it used.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from backtest.runner import BacktestConfig, BacktestSeries, compare, select_policies
from db.tables import seed_rows
from policies.estimators import CANDIDATES
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


def _backtest(series: list[dict[str, Any]], cfg: BacktestConfig) -> dict[str, Any]:
    """Simulated cost (stock-outs, holding, expiry) of the adopted policy per segment on the forecastable series."""
    candidates = [BacktestSeries(s["variant_id"], s["demand"], s["censored"], Decimal(s["price"]), s["segment"]["pattern"], float(s["service_level"]))
                  for s in series if s.get("segment") and s["segment"]["forecast_eligible"] and Decimal(s["price"]) > 0]
    results = compare(candidates, CANDIDATES, cfg)
    adopted = select_policies(results, cfg)
    total, windows = Decimal(0), 0
    for seg, per in results.items():
        cost = per.get(adopted.get(seg, ""), None)
        if cost is not None:
            total += cost.total
            windows += cost.windows
    return {"variants": len(candidates), "windows": windows, "cost": str(total.quantize(Decimal("0.01")))}


def dry_run(conn: Connection, dataset_id: str, series: list[dict[str, Any]], cfg: BacktestConfig | int) -> dict[str, Any]:
    min_history = cfg if isinstance(cfg, int) else cfg.min_history
    bt_cfg = cfg if isinstance(cfg, BacktestConfig) else BacktestConfig(min_history=cfg)
    cand = _rows(conn, dataset_id)
    cur = active_dataset(conn)
    base = _rows(conn, cur.id) if cur is not None and cur.id != dataset_id else {}
    added = [k for k in cand if k not in base]
    removed = [k for k in base if k not in cand]
    changed = [k for k in cand if k in base and base[k] != cand[k]]
    cand_series, cand_rep = apply_seeds(series, _by_variant(cand, dataset_id), min_history)
    base_series, base_rep_ = apply_seeds(series, _by_variant(base, cur.id if cur is not None else ""), min_history) if base else (series, None)
    base_rep = base_rep_
    gained = sorted(cand_rep.used - (base_rep.used if base_rep else set()))
    lost = sorted((base_rep.used if base_rep else set()) - cand_rep.used)
    return {"dataset_id": dataset_id, "compared_with": None if cur is None or cur.id == dataset_id else cur.id,
            "rows": {"added": len(added), "removed": len(removed), "changed": len(changed), "unchanged": len(cand) - len(added) - len(changed)},
            "variants_gaining_history": gained[:200], "variants_losing_history": lost[:200], "skipped_sparse": sorted(cand_rep.skipped_sparse)[:200],
            "overlap": {"variants": cand_rep.overlap_variants, "days": cand_rep.overlap_days},
            "backtest": _comparison(base_series, cand_series, bt_cfg, None if cur is None or cur.id == dataset_id else cur.id)}


def _comparison(base_series: list[dict[str, Any]], cand_series: list[dict[str, Any]], cfg: BacktestConfig, basis: str | None) -> dict[str, Any]:
    before, after = _backtest(base_series, cfg), _backtest(cand_series, cfg)
    enough = before["windows"] > 0 and after["windows"] > 0
    delta = (Decimal(after["cost"]) - Decimal(before["cost"])).quantize(Decimal("0.01")) if enough else None
    return {"status": "ok" if enough else "insufficient_history", "basis": basis or "actual_demand_only", "before": before, "after": after,
            "delta_cost": None if delta is None else str(delta)}
