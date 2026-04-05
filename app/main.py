"""Entry point — App Factory de FastAPI."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.logging import setup_logging
from app.domain.exceptions import DomainException
from app.infrastructure.persistence.database import init_db, close_db
from app.presentation.api.v1.router import api_router
from app.presentation.middleware.error_handler import (
    domain_exception_handler,
    unhandled_exception_handler,
)

settings = get_settings()
setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup y shutdown del application lifecycle."""
    db_url = settings.database_url
    db_type = "postgresql" if "postgresql" in db_url else "sqlite"
    # Ocultar credenciales en el log
    safe_url = db_url.split("@")[-1] if "@" in db_url else db_url
    logger.info(f"[DB] Conectando a {db_type} | {safe_url}")
    await init_db()
    logger.info("[DB] Tablas inicializadas correctamente")
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Sistema de análisis fundamental para acciones chilenas",
        version="0.1.0",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
        lifespan=lifespan,
    )

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.monotonic()
        logger.info(f"→ {request.method} {request.url.path}")
        response = await call_next(request)
        ms = (time.monotonic() - start) * 1000
        logger.info(f"← {request.method} {request.url.path} {response.status_code} ({ms:.0f}ms)")
        return response

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    app.add_exception_handler(DomainException, domain_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # API Routers
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
