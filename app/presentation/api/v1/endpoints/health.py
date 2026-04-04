"""Health check endpoint."""

from fastapi import APIRouter
from app.presentation.schemas.stock import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health() -> HealthResponse:
    return HealthResponse()
