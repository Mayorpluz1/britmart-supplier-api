"""API schemas for BritMart supplier shipments."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.enums import (
    DeliveryPerformance,
    ShipmentStatus,
    StorageType,
)
from app.schemas.common import APIModel, PaginatedResponse


class ShipmentLineResponse(APIModel):
    """Shipment-line representation."""

    shipment_line_id: UUID
    shipment_id: UUID
    shipment_number: str
    purchase_order_id: UUID
    purchase_order_number: str
    purchase_order_line_id: UUID
    line_number: int = Field(ge=1)
    supplier_product_id: UUID
    product_id: UUID
    product_code: str
    sku: str
    storage_type: StorageType
    unit_of_measure: str
    order_multiple: Decimal = Field(gt=0)
    ordered_quantity: Decimal = Field(ge=0)
    planned_quantity: Decimal = Field(ge=0)
    shipped_quantity: Decimal = Field(ge=0)
    received_quantity: Decimal = Field(ge=0)
    damaged_quantity: Decimal = Field(ge=0)
    rejected_quantity: Decimal = Field(ge=0)
    accepted_quantity: Decimal = Field(ge=0)
    created_at: datetime
    updated_at: datetime
    version_number: int = Field(ge=1)


class ShipmentStatusHistoryResponse(APIModel):
    """One shipment status transition."""

    shipment_status_history_id: UUID
    shipment_id: UUID
    shipment_number: str
    sequence_number: int = Field(ge=1)
    previous_status: ShipmentStatus | None = None
    new_status: ShipmentStatus
    status_changed_at: datetime
    changed_by: str
    status_reason: str | None = None
    created_at: datetime


class ShipmentSummaryResponse(APIModel):
    """Shipment representation used by collection endpoints."""

    shipment_id: UUID
    shipment_number: str
    supplier_shipment_reference: str
    purchase_order_id: UUID
    purchase_order_number: str
    supplier_id: UUID
    supplier_code: str
    distribution_centre_id: UUID
    distribution_centre_code: str
    shipment_status: ShipmentStatus
    delivery_performance_status: DeliveryPerformance
    expected_delivery_at: datetime
    actual_delivery_at: datetime | None = None
    total_shipped_quantity: Decimal = Field(ge=0)
    total_received_quantity: Decimal = Field(ge=0)
    total_damaged_quantity: Decimal = Field(ge=0)
    total_rejected_quantity: Decimal = Field(ge=0)
    temperature_controlled_flag: bool
    temperature_breach_flag: bool
    updated_at: datetime
    version_number: int = Field(ge=1)


class ShipmentResponse(ShipmentSummaryResponse):
    """Complete shipment header."""

    carrier_code: str
    carrier_name: str
    vehicle_type: str
    planned_dispatch_at: datetime
    actual_dispatch_at: datetime | None = None
    total_planned_quantity: Decimal = Field(ge=0)
    total_accepted_quantity: Decimal = Field(ge=0)
    minimum_recorded_temperature_celsius: Decimal | None = None
    maximum_recorded_temperature_celsius: Decimal | None = None
    cancellation_reason: str | None = None
    created_at: datetime


class ShipmentDetailResponse(ShipmentResponse):
    """Shipment header with lines and lifecycle history."""

    lines: list[ShipmentLineResponse]
    status_history: list[ShipmentStatusHistoryResponse]


class ShipmentListResponse(
    PaginatedResponse[ShipmentSummaryResponse]
):
    """Paginated shipment response."""


class ShipmentFilterParameters(APIModel):
    """Shipment filters used operationally and by Microsoft Fabric."""

    shipment_status: ShipmentStatus | None = None
    delivery_performance_status: DeliveryPerformance | None = None
    supplier_id: UUID | None = None
    purchase_order_id: UUID | None = None
    distribution_centre_id: UUID | None = None
    temperature_controlled_flag: bool | None = None
    temperature_breach_flag: bool | None = None

    updated_since: datetime | None = None
    updated_before: datetime | None = None

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def validate_incremental_window(
        self,
    ) -> "ShipmentFilterParameters":
        """Validate the incremental extraction window."""

        if (
            self.updated_since is not None
            and self.updated_before is not None
            and self.updated_before <= self.updated_since
        ):
            raise ValueError(
                "updated_before must be later than updated_since."
            )

        return self