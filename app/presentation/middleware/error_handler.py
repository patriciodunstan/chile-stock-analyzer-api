"""Global exception handlers."""

import logging
import traceback

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions import DomainException

logger = logging.getLogger(__name__)


async def domain_exception_handler(
    request: Request, exc: DomainException
) -> JSONResponse:
    logger.warning(
        f"[{exc.__class__.__name__}] {request.method} {request.url.path} → "
        f"{exc.status_code} | {exc.message}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
        },
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    tb = traceback.format_exc()
    logger.error(
        f"[UnhandledException] {request.method} {request.url.path} → 500\n"
        f"  type={type(exc).__name__}\n"
        f"  msg={exc}\n"
        f"  traceback=\n{tb}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
        },
    )
