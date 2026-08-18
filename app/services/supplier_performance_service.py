"""Business services for supplier-performance data."""

from __future__ import annotations

from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.supplier_performance_repository import (
    SupplierPerformanceRepository,
)
from app.schemas.common import PaginationMetadata
from app.schemas.supplier_performance import (
    SupplierPerformanceEventFilterParameters,
    SupplierPerformanceEventListResponse,
    SupplierPerformanceEventResponse,
    SupplierPerformanceMonthlyFilterParameters,
    SupplierPerformanceMonthlyListResponse,
    SupplierPerformanceMonthlyResponse,
)


class SupplierPerformanceService:
    """Coordinate supplier-performance retrieval."""

    def __init__(self, database_session: Session) -> None:
        self.repository = SupplierPerformanceRepository(
            database_session
        )

    def list_events(
        self,
        parameters: SupplierPerformanceEventFilterParameters,
    ) -> SupplierPerformanceEventListResponse:
        """Return a filtered page of performance events."""

        events, total_records = self.repository.list_events(
            parameters
        )

        total_pages = (
            ceil(total_records / parameters.page_size)
            if total_records
            else 0
        )

        return SupplierPerformanceEventListResponse(
            items=[
                SupplierPerformanceEventResponse.model_validate(
                    event
                )
                for event in events
            ],
            pagination=PaginationMetadata(
                page=parameters.page,
                page_size=parameters.page_size,
                total_records=total_records,
                total_pages=total_pages,
                has_next=parameters.page < total_pages,
                has_previous=(
                    parameters.page > 1 and total_pages > 0
                ),
            ),
        )

    def get_event(
        self,
        event_id: UUID,
    ) -> SupplierPerformanceEventResponse:
        """Return one performance event."""

        event = self.repository.get_event_by_id(event_id)

        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PERFORMANCE_EVENT_NOT_FOUND",
                    "message": (
                        f"Supplier-performance event "
                        f"'{event_id}' does not exist."
                    ),
                    "field": (
                        "supplier_performance_event_id"
                    ),
                },
            )

        return SupplierPerformanceEventResponse.model_validate(
            event
        )

    def list_monthly_scorecards(
        self,
        parameters: SupplierPerformanceMonthlyFilterParameters,
    ) -> SupplierPerformanceMonthlyListResponse:
        """Return a filtered monthly-scorecard page."""

        scorecards, total_records = (
            self.repository.list_monthly_scorecards(parameters)
        )

        total_pages = (
            ceil(total_records / parameters.page_size)
            if total_records
            else 0
        )

        return SupplierPerformanceMonthlyListResponse(
            items=[
                SupplierPerformanceMonthlyResponse.model_validate(
                    scorecard
                )
                for scorecard in scorecards
            ],
            pagination=PaginationMetadata(
                page=parameters.page,
                page_size=parameters.page_size,
                total_records=total_records,
                total_pages=total_pages,
                has_next=parameters.page < total_pages,
                has_previous=(
                    parameters.page > 1 and total_pages > 0
                ),
            ),
        )

    def get_monthly_scorecard(
        self,
        scorecard_id: UUID,
    ) -> SupplierPerformanceMonthlyResponse:
        """Return one scorecard by UUID."""

        scorecard = (
            self.repository.get_monthly_scorecard_by_id(
                scorecard_id
            )
        )

        if scorecard is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PERFORMANCE_SCORECARD_NOT_FOUND",
                    "message": (
                        f"Supplier-performance scorecard "
                        f"'{scorecard_id}' does not exist."
                    ),
                    "field": (
                        "supplier_performance_monthly_id"
                    ),
                },
            )

        return SupplierPerformanceMonthlyResponse.model_validate(
            scorecard
        )

    def get_supplier_monthly_scorecard(
        self,
        supplier_id: UUID,
        performance_month: str,
    ) -> SupplierPerformanceMonthlyResponse:
        """Return a supplier scorecard for one month."""

        scorecard = (
            self.repository.get_supplier_monthly_scorecard(
                supplier_id,
                performance_month,
            )
        )

        if scorecard is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PERFORMANCE_SCORECARD_NOT_FOUND",
                    "message": (
                        "No scorecard exists for supplier "
                        f"'{supplier_id}' and month "
                        f"'{performance_month}'."
                    ),
                    "field": "performance_month",
                },
            )

        return SupplierPerformanceMonthlyResponse.model_validate(
            scorecard
        )