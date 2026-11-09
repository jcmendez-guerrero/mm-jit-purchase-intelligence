"""T053 (FR-031, constitution rule 5): money is stored as exact decimals and every timestamp is timezone-aware."""

from db.tables import metadata
from sqlalchemy import DateTime, Double, Float, Numeric

MONEY_WORDS = ("cost", "price", "charge", "threshold", "amount", "total", "value", "fee", "discount", "spend")
NOT_MONEY_FLOATS = {"expected_demand"}                     # a quantity forecast, not an amount of money


def columns():
    return [(t.name, c) for t in metadata.sorted_tables for c in t.columns]


def test_no_column_that_holds_money_is_a_float():
    floats = [f"{t}.{c.name}" for t, c in columns() if isinstance(c.type, (Float, Double)) and c.name not in NOT_MONEY_FLOATS]
    assert floats == [], "use Numeric for money (or add a non-money float to the allowlist with a reason)"
    assert [c.name for _, c in columns() if isinstance(c.type, (Float, Double)) and any(w in c.name for w in MONEY_WORDS)] == []


def test_the_money_columns_of_terms_and_costs_are_exact_decimals():
    named = {(t.name, c.name): c for t, c in ((t, c) for t in metadata.sorted_tables for c in t.columns)}
    for key in [("supplier_terms", "min_order_value"), ("supplier_terms", "free_delivery_threshold"), ("supplier_terms", "delivery_charge"),
                ("supplier_costs", "cost_with_recargo")]:
        assert isinstance(named[key].type, Numeric), key


def test_every_timestamp_column_is_timezone_aware():
    naive = [f"{t}.{c.name}" for t, c in columns() if isinstance(c.type, DateTime) and not c.type.timezone]
    assert naive == []
