"""T070: recargo math (10 % -> 1.4 %, 21 % -> 5.2 %), net <-> gross round trip, unknown VAT rejected."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from costs.recargo import (
    DEFAULT_RATES,
    RecargoTable,
    UnknownVatError,
    display,
    erp_cents,
    gross_from_net,
    load_table,
    net_from_gross,
)
from db.tables import recargo_rates
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import insert

D = Decimal
T = RecargoTable()


def test_the_two_documented_rates():
    assert DEFAULT_RATES == {D("10"): D("1.4"), D("21"): D("5.2")}
    assert T.rate_for(10) == D("1.4") and T.rate_for(D("21.00")) == D("5.2") and T.rate_for("10") == D("1.4")


def test_worked_examples():
    assert gross_from_net("100", D("1.4")) == D("101.4000")
    assert gross_from_net("100", D("5.2")) == D("105.2000")
    assert gross_from_net("2.30", D("5.2")) == D("2.4196")
    assert net_from_gross("105.20", D("5.2")) == D("100.0000")


@pytest.mark.parametrize("vat", [None, 4, 0, D("7.5"), 100])
def test_unknown_or_unconfigured_vat_is_rejected(vat):
    with pytest.raises(UnknownVatError):
        T.rate_for(vat)


def test_floats_are_refused():
    with pytest.raises(TypeError):
        gross_from_net(1.5, D("5.2"))  # type: ignore[arg-type]


@given(st.decimals(min_value=D("0"), max_value=D("100000"), places=4), st.sampled_from([D("1.4"), D("5.2")]))
def test_net_gross_round_trip_stays_within_rounding(net, pct):
    assert abs(net_from_gross(gross_from_net(net, pct), pct) - net) <= D("0.0001")


@given(st.decimals(min_value=D("0"), max_value=D("100000"), places=4), st.sampled_from([D("1.4"), D("5.2")]))
def test_gross_never_below_net_and_scales_with_the_rate(net, pct):
    g = gross_from_net(net, pct)
    assert g >= net and g - net <= net * pct / 100 + D("0.0001")


def test_display_and_erp_value_use_two_decimals_half_up():
    assert display(D("2.4196")) == D("2.42") and display(D("2.425")) == D("2.43") and display(D("2.4249")) == D("2.42")
    assert erp_cents(D("2.4196")) == 242 and erp_cents(D("105.2")) == 10520 and isinstance(erp_cents(D("1")), int)


def test_rates_come_from_a_versioned_table(conn):
    assert load_table(conn).rate_for(21) == D("5.2")
    conn.execute(insert(recargo_rates).values(vat_rate=D("4"), recargo_rate=D("0.5"), valid_from=datetime(2026, 1, 1, tzinfo=UTC), changed_by="admin"))
    conn.execute(insert(recargo_rates).values(vat_rate=D("21"), recargo_rate=D("6.0"), valid_from=datetime(2027, 1, 1, tzinfo=UTC), changed_by="admin"))
    now = datetime(2026, 11, 1, tzinfo=UTC)
    assert load_table(conn, now).rate_for(4) == D("0.5")           # newly configured VAT rate becomes usable
    assert load_table(conn, now).rate_for(21) == D("5.2")          # a future change does not apply yet
    assert load_table(conn, datetime(2027, 2, 1, tzinfo=UTC)).rate_for(21) == D("6.0")
