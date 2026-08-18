"""Liveness and readiness endpoints for the BritMart API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.db.base import utc_now
from app.db.session import check_database_connection
from app.schemas.common import HealthResponse, ReadinessResponse


router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


def application_version() -> str:
    """Return the configured application version with a safe fallback."""

    return str(getattr(settings, "app_version", "1.0.0"))


@router.get(
    "/live",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check application liveness",
    description=(
        "Confirms that the FastAPI process is running. This endpoint does "
        "not test database connectivity and does not require authentication."
    ),
)
def liveness_check() -> HealthResponse:
    """Return the current application liveness status."""

    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        environment=settings.environment,
        version=application_version(),
        timestamp=utc_now(),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The application is running but not ready.",
        }
    },
    summary="Check application readiness",
    description=(
        "Confirms that the application can connect to its operational "
        "database and is ready to serve API requests."
    ),
)
def readiness_check() -> ReadinessResponse:
    """Return readiness status after checking database connectivity."""

    if not check_database_connection():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "DATABASE_UNAVAILABLE",
                "message": (
                    "The application cannot connect to the operational database."
                ),
            },
        )

    return ReadinessResponse(
        status="healthy",
        service=settings.app_name,
        environment=settings.environment,
        version=application_version(),
        timestamp=utc_now(),
        database_status="available",
    )