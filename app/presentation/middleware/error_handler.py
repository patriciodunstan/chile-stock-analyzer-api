"""Global exception handlers."""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions import DomainException

logger = logging.getLogger(__name__)


async def domain_exception_handler(
    request: Request, exc: DomainException
) -> JSONResponse:
    logger.warning(
        f"Domain exception: {exc.message}",
        extra={"path": request.url.path},
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
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
        },
    )
