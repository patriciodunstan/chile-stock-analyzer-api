"""Entry point — App Factory de FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.domain.exceptions import DomainException
from app.infrastructure.persistence.database import init_db, close_db
from app.presentation.api.v1.router import api_router
from app.presentation.middleware.error_handler import (
    domain_exception_handler,
    unhandled_exception_handler,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup y shutdown del application lifecycle."""
    await init_db()
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
