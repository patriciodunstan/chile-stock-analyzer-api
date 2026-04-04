"""Value objects del dominio financiero."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    """Valor monetario inmutable con moneda."""

    amount: float
    currency: str = "CLP"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")

    def to_clp(self, exchange_rate: float = 1.0) -> "Money":
        return Money(amount=self.amount * exchange_rate, currency="CLP")


@dataclass(frozen=True)
class Percentage:
    """Porcentaje inmutable."""

    value: float  # 0.15 = 15%

    @property
    def display(self) -> str:
        return f"{self.value * 100:.2f}%"
