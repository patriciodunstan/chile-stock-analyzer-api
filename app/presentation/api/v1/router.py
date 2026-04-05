"""Router principal v1 — agrega todos los sub-routers."""

from fastapi import APIRouter

from app.presentation.api.v1.endpoints.stocks import router as stocks_router
from app.presentation.api.v1.endpoints.health import router as health_router
from app.presentation.api.v1.endpoints.financials import router as financials_router
from app.presentation.api.v1.endpoints.analysis import router as analysis_router
from app.presentation.api.v1.endpoints.swing import router as swing_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(stocks_router)
api_router.include_router(financials_router)
api_router.include_router(analysis_router)
api_router.include_router(swing_router)
