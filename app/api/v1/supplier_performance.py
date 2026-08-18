"""Version 1 supplier-performance API endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.database import DatabaseSession
from app.dependencies.security import verify_api_key
from app.schemas.common import ErrorResponse
from app.schemas.supplier_performance import (
    SupplierPerformanceEventFilterParameters,
    SupplierPerformanceEventListResponse,
    SupplierPerformanceEventResponse,
    SupplierPerformanceMonthlyFilterParameters,
    SupplierPerformanceMonthlyListResponse,
    SupplierPerformanceMonthlyResponse,
)
from app.services.supplier_performance_service import (
    SupplierPerformanceService,
)


router = APIRouter(
    prefix="/supplier-performance",
    tags=["Supplier Performance"],
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "/events",
    response_model=SupplierPerformanceEventListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def list_supplier_performance_events(
    database_session: DatabaseSession,
    parameters: Annotated[
        SupplierPerformanceEventFilterParameters,
        Query(),
    ],
) -> SupplierPerformanceEventListResponse:
    """Return filtered supplier-performance events."""

    return SupplierPerformanceService(
        database_session
    ).list_events(parameters)


@router.get(
    "/events/{event_id}",
    response_model=SupplierPerformanceEventResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def get_supplier_performance_event(
    event_id: UUID,
    database_session: DatabaseSession,
) -> SupplierPerformanceEventResponse:
    """Return one supplier-performance event."""

    return SupplierPerformanceService(
        database_session
    ).get_event(event_id)


@router.get(
    "/monthly",
    response_model=SupplierPerformanceMonthlyListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def list_supplier_monthly_scorecards(
    database_session: DatabaseSession,
    parameters: Annotated[
        SupplierPerformanceMonthlyFilterParameters,
        Query(),
    ],
) -> SupplierPerformanceMonthlyListResponse:
    """Return monthly supplier-performance scorecards."""

    return SupplierPerformanceService(
        database_session
    ).list_monthly_scorecards(parameters)


@router.get(
    "/monthly/supplier/{supplier_id}",
    response_model=SupplierPerformanceMonthlyResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def get_supplier_monthly_scorecard(
    supplier_id: UUID,
    database_session: DatabaseSession,
    performance_month: Annotated[
        str,
        Query(pattern=r"^\d{4}-\d{2}$"),
    ],
) -> SupplierPerformanceMonthlyResponse:
    """Return one supplier's scorecard for a given month."""

    return SupplierPerformanceService(
        database_session
    ).get_supplier_monthly_scorecard(
        supplier_id,
        performance_month,
    )


@router.get(
    "/monthly/{scorecard_id}",
    response_model=SupplierPerformanceMonthlyResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def get_monthly_scorecard(
    scorecard_id: UUID,
    database_session: DatabaseSession,
) -> SupplierPerformanceMonthlyResponse:
    """Return one monthly scorecard by UUID."""

    return SupplierPerformanceService(
        database_session
    ).get_monthly_scorecard(scorecard_id)