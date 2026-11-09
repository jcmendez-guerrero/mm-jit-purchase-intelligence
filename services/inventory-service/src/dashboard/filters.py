"""T008: the one validated filter set every dashboard figure, drill-down and export takes (spec FR-006, data-model FilterSet).

Invalid values are refused with ``request_invalid``; nothing is coerced silently except an end date in the future, which is clipped to today and reported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from dashboard.kpis import CATEGORIES, Filters

DEFAULT_DAYS = 60
MIN_SPAN_DAYS = 7
MAX_SPAN_DAYS = 730
_SUPPLIER = re.compile(r"^[A-Za-z0-9_-]{1,36}$")


class FilterError(ValueError):
    code = "request_invalid"


@dataclass(frozen=True)
class FilterSet:
    date_from: date
    date_to: date
    warehouse_id: int | None = None
    supplier_id: str | None = None
    category: str | None = None
    family: str | None = None
    clipped_to_today: bool = False

    @classmethod
    def parse(cls, today: date, date_from: date | None = None, date_to: date | None = None, warehouse_id: int | None = None,
              supplier_id: str | None = None, category: str | None = None, family: str | None = None) -> FilterSet:
        clipped = False
        end = date_to or today
        if end > today:
            end, clipped = today, True
        start = date_from or end - timedelta(days=DEFAULT_DAYS - 1)
        if start > end:
            raise FilterError("date_from after date_to")
        if not MIN_SPAN_DAYS <= (end - start).days + 1 <= MAX_SPAN_DAYS:
            raise FilterError("date range span")
        if warehouse_id is not None and warehouse_id < 0:
            raise FilterError("warehouse")
        if supplier_id is not None and not _SUPPLIER.match(supplier_id):
            raise FilterError("supplier")
        if category is not None and category not in CATEGORIES:
            raise FilterError("category")
        if family is not None and not 0 < len(family) <= 120:
            raise FilterError("family")
        return cls(start, end, warehouse_id, supplier_id, category, family, clipped)

    def to_filters(self) -> Filters:
        return Filters(self.warehouse_id, self.category, self.family, self.supplier_id)
