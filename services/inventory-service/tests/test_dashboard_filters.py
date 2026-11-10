"""T009: FilterSet validation (ranges, spans, unknown ids, hostile strings)."""

from datetime import date

import pytest
from dashboard.filters import FilterError, FilterSet
from reference_dataset import TODAY


def test_defaults_to_the_last_sixty_days_ending_today():
    f = FilterSet.parse(TODAY)
    assert f.date_to == TODAY and (f.date_to - f.date_from).days + 1 == 60 and not f.clipped_to_today


def test_a_future_end_date_is_clipped_and_reported():
    f = FilterSet.parse(TODAY, date_from=date(2026, 10, 1), date_to=date(2027, 1, 1))
    assert f.date_to == TODAY and f.clipped_to_today


@pytest.mark.parametrize("start,end", [(date(2026, 11, 9), date(2026, 11, 1)), (date(2026, 11, 8), date(2026, 11, 9)), (date(2020, 1, 1), date(2026, 11, 9))])
def test_inverted_too_short_or_too_long_ranges_are_refused(start, end):
    with pytest.raises(FilterError):
        FilterSet.parse(TODAY, date_from=start, date_to=end)


@pytest.mark.parametrize("kw", [{"warehouse_id": -1}, {"category": "Z"}, {"family": ""}, {"family": "x" * 121}, {"supplier_id": "a b"}, {"supplier_id": "x'; DROP TABLE variants;--"},
                                {"supplier_id": "x" * 37}])
def test_bad_values_are_refused_not_coerced(kw):
    with pytest.raises(FilterError):
        FilterSet.parse(TODAY, **kw)


def test_converts_to_the_filters_the_figures_use():
    f = FilterSet.parse(TODAY, warehouse_id=2, supplier_id="sup-b", category="A", family="Fam").to_filters()
    assert (f.warehouse_id, f.supplier_id, f.category, f.family) == (2, "sup-b", "A", "Fam")
