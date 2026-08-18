"""API schemas for BritMart purchase-order resources."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, model_validator

from app.models.enums import (
    CurrencyCode,
    PurchaseOrderStatus,
    PurchaseOrderType,
)
from app.schemas.common import APIModel, PaginatedResponse


class PurchaseOrderLineResponse(APIModel):
    """Purchase-order line returned by the API."""

    purchase_order_line_id: UUID
    purchase_order_id: UUID
    purchase_order_number: str

    line_number: int = Field(ge=1)

    supplier_product_id: UUID
    product_id: UUID
    product_code: str
    sku: str

    ordered_quantity: Decimal = Field(ge=0)
    unit_of_measure: str
    order_multiple: Decimal = Field(gt=0)

    unit_price: Decimal = Field(ge=0)
    currency_code: CurrencyCode

    net_amount: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(ge=0)
    vat_amount: Decimal = Field(ge=0)
    gross_amount: Decimal = Field(ge=0)

    created_at: datetime
    updated_at: datetime
    version_number: int = Field(ge=1)


class PurchaseOrderSummaryResponse(APIModel):
    """Reduced purchase-order representation used in collections."""

    purchase_order_id: UUID
    purchase_order_number: str

    supplier_id: UUID
    supplier_code: str

    distribution_centre_id: UUID
    distribution_centre_code: str

    order_date: date
    required_delivery_date: date

    order_type: PurchaseOrderType
    purchase_order_status: PurchaseOrderStatus
    currency_code: CurrencyCode

    total_net_amount: Decimal = Field(ge=0)
    total_vat_amount: Decimal = Field(ge=0)
    total_gross_amount: Decimal = Field(ge=0)
    total_value_gbp: Decimal = Field(ge=0)

    updated_at: datetime
    version_number: int = Field(ge=1)


class PurchaseOrderResponse(PurchaseOrderSummaryResponse):
    """Complete purchase-order header returned by the API."""

    buyer_code: str
    approval_role: str
    approved_at: datetime | None = None
    cancellation_reason: str | None = None

    created_by: str
    updated_by: str

    created_at: datetime


class PurchaseOrderDetailResponse(PurchaseOrderResponse):
    """Purchase-order header together with its ordered lines."""

    lines: list[PurchaseOrderLineResponse]


class PurchaseOrderListResponse(
    PaginatedResponse[PurchaseOrderSummaryResponse]
):
    """Paginated purchase-order collection response."""


class PurchaseOrderFilterParameters(APIModel):
    """Filtering and incremental extraction parameters."""

    purchase_order_status: PurchaseOrderStatus | None = None
    order_type: PurchaseOrderType | None = None

    supplier_id: UUID | None = None
    distribution_centre_id: UUID | None = None

    order_date_from: date | None = None
    order_date_to: date | None = None

    updated_since: datetime | None = Field(
        default=None,
        description=(
            "Inclusive UTC lower watermark. Results are ordered by "
            "updated_at followed by purchase_order_id."
        ),
    )
    updated_before: datetime | None = Field(
        default=None,
        description="Exclusive UTC upper extraction boundary.",
    )

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def validate_filter_windows(
        self,
    ) -> "PurchaseOrderFilterParameters":
        """Validate business-date and incremental extraction windows."""

        if (
            self.order_date_from is not None
            and self.order_date_to is not None
            and self.order_date_to < self.order_date_from
        ):
            raise ValueError(
                "order_date_to must be on or after order_date_from."
            )

        if (
            self.updated_since is not None
            and self.updated_before is not None
            and self.updated_before <= self.updated_since
        ):
            raise ValueError(
                "updated_before must be later than updated_since."
            )

        return self