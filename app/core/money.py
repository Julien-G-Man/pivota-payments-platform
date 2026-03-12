"""
Money class — the most important file in the codebase.

All financial values pass through this. Float is NEVER accepted.
See CLAUDE.md Rule 1.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from dataclasses import dataclass
from typing import Union

from app.core.exceptions import FloatMoneyError, CurrencyMismatchError

SUPPORTED_CURRENCIES = {"GHS", "USD", "EUR"}
MINOR_UNIT_FACTORS: dict[str, int] = {"GHS": 100, "USD": 100, "EUR": 100}


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "GHS"

    def __new__(
        cls,
        amount: Union[str, int, Decimal],
        currency: str = "GHS",
        unit: str = "major",
    ) -> "Money":
        if isinstance(amount, float):
            raise FloatMoneyError(
                f"Float passed to Money({amount}). Use string, int, or Decimal. "
                "Floats cause precision loss in financial calculations."
            )
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency: {currency}")

        instance = object.__new__(cls)
        try:
            if unit == "minor":
                factor = MINOR_UNIT_FACTORS[currency]
                decimal_amount = Decimal(str(amount)) / Decimal(str(factor))
            else:
                decimal_amount = Decimal(str(amount))
        except InvalidOperation:
            raise ValueError(f"Cannot convert {amount!r} to Decimal")

        object.__setattr__(
            instance,
            "amount",
            decimal_amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        )
        object.__setattr__(instance, "currency", currency)
        return instance

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot add {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot subtract {self.currency} and {other.currency}"
            )
        return Money(self.amount - other.amount, self.currency)

    def __gt__(self, other: "Money") -> bool:
        return self.amount > other.amount

    def __lt__(self, other: "Money") -> bool:
        return self.amount < other.amount

    def format(self) -> str:
        """Human-readable. Always use this for display — never .amount directly."""
        return f"{self.currency} {self.amount:.2f}"

    def to_minor_units(self) -> int:
        """Returns integer minor units (pesewas for GHS). Use for storage comparisons."""
        factor = MINOR_UNIT_FACTORS[self.currency]
        return int(self.amount * factor)

    @classmethod
    def from_db(cls, amount: Decimal, currency: str = "GHS") -> "Money":
        """Use this when reading Numeric values from SQLAlchemy — already Decimal."""
        return cls(amount, currency)

    def __repr__(self) -> str:
        return f"Money({self.amount!r}, {self.currency!r})"
