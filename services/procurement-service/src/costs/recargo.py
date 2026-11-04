"""T074: Recargo de Equivalencia arithmetic. Decimal only; rates live in a versioned table, not in code paths.

Default rates (as stated by the business): VAT 10 % -> recargo 1.4 %, VAT 21 % -> 5.2 %. Any other VAT rate is rejected
for a net entry because its recargo has not been specified (open item V5): the buyer can still enter a cost that already
includes recargo. Rounding: half-up to 4 decimals internally, 2 decimals for display and for the value written to the ERP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from db.tables import recargo_rates
from sqlalchemy import select
from sqlalchemy.engine import Connection

Q4, Q2 = Decimal("0.0001"), Decimal("0.01")
DEFAULT_RATES: dict[Decimal, Decimal] = {Decimal("10"): Decimal("1.4"), Decimal("21"): Decimal("5.2")}


class UnknownVatError(ValueError):
    """The product's VAT rate is unknown or has no configured recargo."""


def _d(value: Decimal | int | str) -> Decimal:
    if isinstance(value, float):
        raise TypeError("floats are not allowed for money")
    return value if isinstance(value, Decimal) else Decimal(str(value))


@dataclass(frozen=True)
class RecargoTable:
    rates: dict[Decimal, Decimal] = field(default_factory=lambda: dict(DEFAULT_RATES))

    def rate_for(self, vat_rate: Decimal | int | str | None) -> Decimal:
        """Recargo percent for a VAT percent; raises ``UnknownVatError`` when it cannot be determined."""
        if vat_rate is None:
            raise UnknownVatError("VAT rate unknown")
        try:
            return self.rates[_d(vat_rate).normalize()]
        except KeyError:
            raise UnknownVatError(f"no recargo configured for VAT {vat_rate}") from None


def load_table(conn: Connection, as_of: datetime | None = None) -> RecargoTable:
    """Defaults overridden by the latest configured row per VAT rate valid at ``as_of``."""
    as_of = as_of or datetime.now(UTC)
    rates = {k.normalize(): v for k, v in DEFAULT_RATES.items()}
    rows = conn.execute(select(recargo_rates).order_by(recargo_rates.c.valid_from, recargo_rates.c.id)).all()
    for r in rows:
        valid = r.valid_from if r.valid_from.tzinfo else r.valid_from.replace(tzinfo=UTC)
        if valid <= as_of:
            rates[Decimal(str(r.vat_rate)).normalize()] = Decimal(str(r.recargo_rate))
    return RecargoTable(rates)


def gross_from_net(net: Decimal | int | str, recargo_pct: Decimal) -> Decimal:
    return (_d(net) * (1 + _d(recargo_pct) / 100)).quantize(Q4, rounding=ROUND_HALF_UP)


def net_from_gross(gross: Decimal | int | str, recargo_pct: Decimal) -> Decimal:
    return (_d(gross) / (1 + _d(recargo_pct) / 100)).quantize(Q4, rounding=ROUND_HALF_UP)


def display(amount: Decimal) -> Decimal:
    return _d(amount).quantize(Q2, rounding=ROUND_HALF_UP)


def erp_cents(gross: Decimal) -> int:
    """Whole cents written to Siweb: the 2-decimal display value times 100."""
    return int((display(gross) * 100).to_integral_value(rounding=ROUND_HALF_UP))
