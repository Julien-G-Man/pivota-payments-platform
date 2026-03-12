"""Tests for app.core.money — 100% coverage required."""

import pytest
from decimal import Decimal

from app.core.money import Money
from app.core.exceptions import FloatMoneyError, CurrencyMismatchError


def test_float_is_rejected():
    with pytest.raises(FloatMoneyError):
        Money(29.99)  # type: ignore[arg-type]


def test_string_amount():
    m = Money("29.99")
    assert m.amount == Decimal("29.9900")
    assert m.currency == "GHS"


def test_integer_amount():
    m = Money(100)
    assert m.amount == Decimal("100.0000")


def test_minor_units():
    m = Money(2999, unit="minor")
    assert m.amount == Decimal("29.9900")


def test_addition():
    a = Money("10.00")
    b = Money("5.50")
    assert (a + b).amount == Decimal("15.5000")


def test_subtraction():
    a = Money("20.00")
    b = Money("7.25")
    assert (a - b).amount == Decimal("12.7500")


def test_currency_mismatch_raises():
    a = Money("10.00", "GHS")
    b = Money("10.00", "USD")
    with pytest.raises(CurrencyMismatchError):
        _ = a + b


def test_format():
    m = Money("1234.5678")
    assert m.format() == "GHS 1234.57"


def test_from_db():
    m = Money.from_db(Decimal("99.9900"))
    assert m.currency == "GHS"
    assert m.amount == Decimal("99.9900")


def test_unsupported_currency():
    with pytest.raises(ValueError):
        Money("10.00", "XYZ")
