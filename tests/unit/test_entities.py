"""Tests de entidades de dominio."""

from __future__ import annotations

from app.domain.entities.stock import StockPrice
from app.domain.entities.financial import FinancialStatement
from app.domain.value_objects.money import Money, Percentage


def test_stock_price_is_valid():
    price = StockPrice(ticker="SQM-B", price=55000.0, volume=1000)
    assert price.is_valid is True


def test_stock_price_invalid_when_zero():
    price = StockPrice(ticker="SQM-B", price=0.0)
    assert price.is_valid is False


def test_stock_price_invalid_when_no_ticker():
    price = StockPrice(ticker="", price=100.0)
    assert price.is_valid is False


def test_financial_enterprise_value():
    stmt = FinancialStatement(
        ticker="BCI",
        total_debt=5_000_000,
        cash_and_equivalents=1_000_000,
    )
    assert stmt.enterprise_value == 4_000_000


def test_money_value_object():
    money = Money(amount=1000.0, currency="CLP")
    assert money.amount == 1000.0
    assert money.currency == "CLP"


def test_money_cannot_be_negative():
    import pytest

    with pytest.raises(ValueError):
        Money(amount=-100.0)


def test_percentage_display():
    pct = Percentage(value=0.15)
    assert pct.display == "15.00%"
