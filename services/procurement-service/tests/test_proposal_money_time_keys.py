"""T044 (FR-012): exact decimal money, UTC timestamps and variant-id keys in the proposal domain; users see the SKU."""

from decimal import Decimal

from db.tables import proposal_lines, proposals
from proposal_support import generate, h
from sqlalchemy import Numeric


def test_money_columns_of_proposals_and_lines_are_exact_decimals_never_floats():
    from sqlalchemy import Float

    for table in (proposals, proposal_lines):
        for col in table.columns:
            assert not isinstance(col.type, Float), f"{table.name}.{col.name} is a float"
    assert isinstance(proposal_lines.c.unit_cost_with_recargo.type, Numeric) and isinstance(proposal_lines.c.line_total.type, Numeric)


def test_a_line_is_keyed_by_variant_id_shows_the_sku_and_money_is_a_decimal_string(api):
    c, _ = api
    pid = generate(c)
    line = c.get(f"/proposals/{pid}", headers=h("viewer")).json()["lines"][0]
    assert isinstance(line["variant_id"], int) and "sku" in line
    assert Decimal(line["unit_cost_with_recargo"]) == Decimal("1.00") and Decimal(line["line_total"]) == Decimal(line["unit_cost_with_recargo"]) * line["qty"]


def test_proposal_timestamp_columns_are_timezone_aware():
    """The test database (SQLite) drops zones when reading back, so the column type is what is checked; PostgreSQL stores timestamptz."""
    from db.tables import approvals
    from sqlalchemy import DateTime

    for table in (proposals, approvals):
        for col in table.columns:
            if isinstance(col.type, DateTime):
                assert col.type.timezone, f"{table.name}.{col.name} is not timezone-aware"
