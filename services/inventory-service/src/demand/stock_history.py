"""T053: rebuild daily on-hand history backwards from the current snapshot and mark censored days.

close[D] = current_on_hand - sum(net movement after D); open[D] = close[D] - net[D].
A day is censored (demand not observable) when the stock was at or below zero at its start or end;
the opening balance of the very first day is zero by definition (nothing existed yet) and does not count.
reconciled_ok is False when the history cannot be trusted: the balance before the first movement is not zero
(history is incomplete), an earlier forward snapshot disagrees, or a movement has no usable date. Such variants
must not be forecast.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from demand.common import Mov


@dataclass(frozen=True)
class HistoryRow:
    variant_id: int
    day: date
    on_hand: int
    censored: bool
    reconciled_ok: bool


def reconstruct(
    movements: Iterable[Mov],
    current_on_hand: Mapping[int, int],
    through_day: date,
    snapshots: Mapping[int, Mapping[date, int]] | None = None,
    min_run: int = 1,
) -> list[HistoryRow]:
    """``movements`` must include quarantined ones: stock moved physically whatever the review outcome."""
    net: dict[int, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    undated: set[int] = set()
    for m in movements:
        if m.day is None:
            undated.add(m.variant_id)
        elif m.day <= through_day:
            net[m.variant_id][m.day] += m.quantity
    rows: list[HistoryRow] = []
    for vid, per_day in net.items():
        if vid not in current_on_hand:
            continue
        first = min(per_day)
        close = current_on_hand[vid]
        series: list[tuple[date, int, int]] = []  # (day, open, close) newest first
        d = through_day
        while d >= first:
            opening = close - per_day.get(d, 0)
            series.append((d, opening, close))
            close = opening
            d -= timedelta(days=1)
        ok = vid not in undated and series[-1][1] == 0  # nothing should exist before the first movement
        by_day = {day: cl for day, _, cl in series}
        for snap_day, snap_qty in (snapshots or {}).get(vid, {}).items():
            if snap_day in by_day and by_day[snap_day] != snap_qty:
                ok = False
        flags = [(op <= 0 and day != first) or cl <= 0 for day, op, cl in reversed(series)]
        if min_run > 1:                                   # short stock-outs are not treated as hidden demand (rule min_zero_stock_days)
            i = 0
            while i < len(flags):
                if flags[i]:
                    j = i
                    while j < len(flags) and flags[j]:
                        j += 1
                    if j - i < min_run:
                        flags[i:j] = [False] * (j - i)
                    i = j
                else:
                    i += 1
        rows += [HistoryRow(vid, day, cl, flags[k], ok) for k, (day, _op, cl) in enumerate(reversed(series))]
    return rows
