"""MMI-6 (FR-020, US5-2): the supplier's order days, order cutoff and delivery weekdays turned into dates.

Pure functions, no I/O, so the proposal stays reproducible. Weekdays are ISO numbers 1 (Monday) to 7 (Sunday). The cutoff is a local
"HH:MM" (Europe/Madrid until the ERP's time zone is verified); an order placed exactly at the cutoff still counts as before it.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from mmi_common.time import ASSUMED_LOCAL_TZ

__all__ = ["delivery_date", "next_order_date", "order_date_from"]


def _cutoff(text: str) -> time:
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))


def next_order_date(placed: datetime, order_days: tuple[int, ...], cutoff: str | None) -> date:
    """The first day on which an order placed at ``placed`` is accepted: an order day, and today only if before the cutoff.

    Only the wall-clock date and time of ``placed`` are read, so pass the local business time (see ``order_date_from`` for a UTC moment).
    """
    today = placed.date()
    for offset in range(8):
        day = today + timedelta(days=offset)
        if order_days and day.isoweekday() not in order_days:
            continue
        if offset == 0 and cutoff is not None and placed.time() > _cutoff(cutoff):
            continue
        return day
    return today                                                     # not reachable for valid weekdays 1..7


def delivery_date(order: date, lead_days: int, delivery_weekdays: tuple[int, ...]) -> date:
    """The order date plus the lead time, moved forward to the next delivery weekday when the supplier delivers on fixed days."""
    day = order + timedelta(days=lead_days)
    for _ in range(7):
        if not delivery_weekdays or day.isoweekday() in delivery_weekdays:
            return day
        day += timedelta(days=1)
    return day


def order_date_from(now: datetime, order_days: tuple[int, ...], cutoff: str | None) -> date:
    """``next_order_date`` for an aware moment such as 'now': the cutoff is read in local business time, not UTC."""
    local = now.astimezone(ZoneInfo(ASSUMED_LOCAL_TZ)).replace(tzinfo=None) if now.tzinfo else now
    return next_order_date(local, order_days, cutoff)
