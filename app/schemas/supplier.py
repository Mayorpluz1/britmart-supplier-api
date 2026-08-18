"""API schemas for BritMart supplier resources."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import EmailStr, Field, model_validator

from app.models.enums import (
    CurrencyCode,
    SupplierRiskRating,
    SupplierStatus,
)
from app.schemas.common import APIModel, PaginatedResponse


class SupplierResponse(APIModel):
    """Complete supplier representation returned by the API."""

    supplier_id: UUID
    supplier_code: str = Field(min_length=1, max_length=30)
    supplier_name: str = Field(min_length=1, max_length=200)
    legal_name: str = Field(min_length=1, max_length=250)
    supplier_type: str = Field(min_length=1, max_length=50)

    category_codes: list[str] = Field(
        description="Product categories that the supplier can provide."
    )

    country_code: str = Field(
        min_length=2,
        max_length=2,
        description="ISO two-character supplier country code.",
    )
    origin_group: str = Field(min_length=1, max_length=30)
    default_currency_code: CurrencyCode

    standard_lead_time_days: int = Field(ge=0)
    minimum_order_value: Decimal = Field(ge=0)

    supports_ambient: bool
    supports_chilled: bool
    supports_frozen: bool

    risk_rating: SupplierRiskRating
    supplier_status: SupplierStatus
    active_flag: bool

    payment_terms_days: int = Field(ge=0)
    incoterm: str = Field(min_length=1, max_length=20)

    target_otif_rate: Decimal = Field(ge=0, le=1)
    target_quality_acceptance_rate: Decimal = Field(ge=0, le=1)

    contact_email: EmailStr

    effective_from: date
    effective_to: date | None = None

    created_at: datetime
    updated_at: datetime
    version_number: int = Field(ge=1)


class SupplierSummaryResponse(APIModel):
    """Reduced supplier representation used in collection endpoints."""

    supplier_id: UUID
    supplier_code: str
    supplier_name: str
    supplier_type: str
    country_code: str
    default_currency_code: CurrencyCode
    risk_rating: SupplierRiskRating
    supplier_status: SupplierStatus
    active_flag: bool
    updated_at: datetime
    version_number: int


class SupplierListResponse(
    PaginatedResponse[SupplierSummaryResponse]
):
    """Paginated response returned by the supplier collection endpoint."""


class SupplierFilterParameters(APIModel):
    """Supported filtering and incremental-extraction parameters."""

    supplier_status: SupplierStatus | None = None
    risk_rating: SupplierRiskRating | None = None
    country_code: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
    )
    active_flag: bool | None = None

    updated_since: datetime | None = Field(
        default=None,
        description=(
            "Inclusive UTC lower watermark. Results are ordered by "
            "updated_at followed by supplier_id."
        ),
    )
    updated_before: datetime | None = Field(
        default=None,
        description="Exclusive UTC upper boundary for the extraction window.",
    )

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=500)

    @model_validator(mode="after")
    def validate_incremental_window(
        self,
    ) -> "SupplierFilterParameters":
        """Confirm that the incremental extraction window is valid."""

        if (
            self.updated_since is not None
            and self.updated_before is not None
            and self.updated_before <= self.updated_since
        ):
            raise ValueError(
                "updated_before must be later than updated_since."
            )

        return self