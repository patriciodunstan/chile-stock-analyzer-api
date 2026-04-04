from __future__ import annotations
"""Excepciones de dominio del sistema de análisis fundamental."""

from typing import Any


class DomainException(Exception):
    """Base para todas las excepciones de dominio."""

    status_code: int = 400
    message: str = "Domain error"
    details: dict[str, Any] | None = None

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)


class NotFoundError(DomainException):
    status_code = 404
    message = "Resource not found"


class TickerNotFoundError(NotFoundError):
    message = "Ticker not found in Bolsa de Santiago"


class ExternalAPIError(DomainException):
    status_code = 502
    message = "External API error"


class InsufficientDataError(DomainException):
    status_code = 422
    message = "Insufficient financial data for analysis"
