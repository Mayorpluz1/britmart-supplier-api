"""Business services for BritMart shipments."""

from __future__ import annotations

from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.shipment_repository import ShipmentRepository
from app.schemas.common import PaginationMetadata
from app.schemas.shipment import (
    ShipmentDetailResponse,
    ShipmentFilterParameters,
    ShipmentLineResponse,
    ShipmentListResponse,
    ShipmentStatusHistoryResponse,
    ShipmentSummaryResponse,
)


class ShipmentService:
    """Coordinate shipment retrieval and API responses."""

    def __init__(self, database_session: Session) -> None:
        self.repository = ShipmentRepository(database_session)

    def list_shipments(
        self,
        parameters: ShipmentFilterParameters,
    ) -> ShipmentListResponse:
        """Return a filtered shipment page."""

        shipments, total_records = self.repository.list_shipments(
            parameters
        )
        total_pages = (
            ceil(total_records / parameters.page_size)
            if total_records
            else 0
        )

        return ShipmentListResponse(
            items=[
                ShipmentSummaryResponse.model_validate(shipment)
                for shipment in shipments
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

    def _build_detail(
        self,
        shipment_id: UUID,
    ) -> ShipmentDetailResponse:
        """Build a shipment with lines and status history."""

        shipment = self.repository.get_by_id(shipment_id)

        if shipment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "SHIPMENT_NOT_FOUND",
                    "message": (
                        f"Shipment '{shipment_id}' does not exist."
                    ),
                    "field": "shipment_id",
                },
            )

        values = {
            column.name: getattr(shipment, column.name)
            for column in shipment.__table__.columns
        }
        values["lines"] = [
            ShipmentLineResponse.model_validate(line)
            for line in self.repository.list_lines(shipment_id)
        ]
        values["status_history"] = [
            ShipmentStatusHistoryResponse.model_validate(event)
            for event in self.repository.list_status_history(
                shipment_id
            )
        ]

        return ShipmentDetailResponse.model_validate(values)

    def get_shipment(
        self,
        shipment_id: UUID,
    ) -> ShipmentDetailResponse:
        """Return one shipment by UUID."""

        return self._build_detail(shipment_id)

    def get_shipment_by_number(
        self,
        shipment_number: str,
    ) -> ShipmentDetailResponse:
        """Return one shipment by business number."""

        normalised_number = shipment_number.strip().upper()
        shipment = self.repository.get_by_number(normalised_number)

        if shipment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "SHIPMENT_NOT_FOUND",
                    "message": (
                        f"Shipment number '{normalised_number}' "
                        "does not exist."
                    ),
                    "field": "shipment_number",
                },
            )

        return self._build_detail(shipment.shipment_id)