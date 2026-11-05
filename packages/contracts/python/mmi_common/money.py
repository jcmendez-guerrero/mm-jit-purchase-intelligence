"""Decimal money. Floats are rejected everywhere (constitution: decimal arithmetic)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

Q4 = Decimal("0.0001")
Q2 = Decimal("0.01")


def to_decimal(value: Decimal | int | str) -> Decimal:
    """Convert to Decimal; refuses float and bool so binary rounding never enters."""
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("floats are not allowed for money; use Decimal, int or str")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"not a decimal: {value!r}") from exc


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "EUR"

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", to_decimal(self.amount))
        if len(self.currency) != 3 or not self.currency.isupper() or not self.currency.isalpha():
            raise ValueError("currency must be an ISO 4217 code")

    @classmethod
    def from_cents(cls, cents: Decimal | int | str, currency: str = "EUR") -> Money:
        """Siweb gives costs in cents, possibly fractional."""
        return cls(to_decimal(cents) / Decimal(100), currency)

    @classmethod
    def parse(cls, amount: str, currency: str = "EUR") -> Money:
        return cls(to_decimal(amount), currency)

    def _check(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError("currency mismatch")

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount - other.amount, self.currency)

    def times(self, factor: Decimal | int | str) -> Money:
        return Money(self.amount * to_decimal(factor), self.currency)

    def rounded(self, places: int = 4) -> Money:
        q = Q4 if places == 4 else Q2 if places == 2 else Decimal(1).scaleb(-places)
        return Money(self.amount.quantize(q, rounding=ROUND_HALF_UP), self.currency)

    def to_cents(self) -> int:
        """Half-up to whole cents."""
        return int((self.amount * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))

    def to_dto(self) -> dict[str, str]:
        return {"amount": format(self.rounded(4).amount, "f"), "currency": self.currency}
