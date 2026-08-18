"""API schemas for supplier-performance data."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.enums import (
    PerformanceEventCategory,
    PerformanceEventSeverity,
    PerformanceRating,
    PerformanceRiskIndicator,
)
from app.schemas.common import APIModel, PaginatedResponse


class SupplierPerformanceEventResponse(APIModel):
    """Supplier-performance event returned by the API."""

    supplier_performance_event_id: UUID
    event_number: str
    supplier_id: UUID
    supplier_code: str
    event_type: str
    event_category: PerformanceEventCategory
    severity: PerformanceEventSeverity
    source_system: str

    shipment_id: UUID | None = None
    shipment_number: str | None = None
    purchase_order_id: UUID | None = None
    purchase_order_number: str | None = None
    goods_receipt_id: UUID | None = None
    goods_receipt_number: str | None = None

    event_occurred_at: datetime
    performance_month: str
    metric_name: str
    metric_actual_value: Decimal | None = None
    metric_target_value: Decimal | None = None
    passed_flag: bool
    score_impact: Decimal
    event_description: str
    idempotency_key: str
    created_at: datetime
    updated_at: datetime
    version_number: int


class SupplierPerformanceMonthlyResponse(APIModel):
    """Monthly supplier scorecard returned by the API."""

    supplier_performance_monthly_id: UUID
    supplier_id: UUID
    supplier_code: str
    performance_month: str

    delivery_count: int
    early_delivery_count: int
    on_time_delivery_count: int
    late_delivery_count: int

    evaluated_purchase_order_count: int
    otif_pass_count: int
    otif_fail_count: int
    in_full_pass_count: int
    in_full_fail_count: int

    total_received_quantity: Decimal
    total_accepted_quantity: Decimal
    total_damaged_quantity: Decimal
    total_rejected_quantity: Decimal

    temperature_controlled_delivery_count: int
    temperature_breach_count: int

    on_time_delivery_rate: Decimal
    in_full_rate: Decimal
    otif_rate: Decimal
    accepted_quality_rate: Decimal
    damage_rate: Decimal
    rejection_rate: Decimal
    temperature_compliance_rate: Decimal

    performance_score: Decimal
    performance_rating: PerformanceRating
    risk_indicator: PerformanceRiskIndicator

    idempotency_key: str
    created_at: datetime
    updated_at: datetime
    version_number: int


class SupplierPerformanceEventListResponse(
    PaginatedResponse[SupplierPerformanceEventResponse]
):
    """Paginated supplier-performance event response."""


class SupplierPerformanceMonthlyListResponse(
    PaginatedResponse[SupplierPerformanceMonthlyResponse]
):
    """Paginated monthly supplier-scorecard response."""


class SupplierPerformanceEventFilterParameters(APIModel):
    """Filtering and incremental extraction parameters for events."""

    supplier_id: UUID | None = None
    supplier_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=20,
    )
    event_category: PerformanceEventCategory | None = None
    severity: PerformanceEventSeverity | None = None
    passed_flag: bool | None = None
    performance_month: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}$",
    )
    shipment_id: UUID | None = None
    purchase_order_id: UUID | None = None
    event_occurred_since: datetime | None = None
    event_occurred_before: datetime | None = None
    updated_since: datetime | None = None
    updated_before: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def validate_windows(
        self,
    ) -> "SupplierPerformanceEventFilterParameters":
        """Ensure extraction windows have valid boundaries."""

        if (
            self.updated_since is not None
            and self.updated_before is not None
            and self.updated_before <= self.updated_since
        ):
            raise ValueError(
                "updated_before must be later than updated_since."
            )

        if (
            self.event_occurred_since is not None
            and self.event_occurred_before is not None
            and self.event_occurred_before
            <= self.event_occurred_since
        ):
            raise ValueError(
                "event_occurred_before must be later than "
                "event_occurred_since."
            )

        return self


class SupplierPerformanceMonthlyFilterParameters(APIModel):
    """Filtering and incremental extraction parameters for scorecards."""

    supplier_id: UUID | None = None
    supplier_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=20,
    )
    performance_month: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}$",
    )
    performance_rating: PerformanceRating | None = None
    risk_indicator: PerformanceRiskIndicator | None = None
    updated_since: datetime | None = None
    updated_before: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def validate_incremental_window(
        self,
    ) -> "SupplierPerformanceMonthlyFilterParameters":
        """Ensure the incremental window has valid boundaries."""

        if (
            self.updated_since is not None
            and self.updated_before is not None
            and self.updated_before <= self.updated_since
        ):
            raise ValueError(
                "updated_before must be later than updated_since."
            )

        return self