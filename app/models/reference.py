"""Synchronised reference models mastered outside the Supplier API."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, utc_now
from app.models.enums import StorageType


class ProductReference(AuditMixin, Base):
    """
    Read-only product reference copied from the SQL operational system.

    Product commercial and descriptive attributes are not mastered by
    the Supplier API.
    """

    __tablename__ = "product_reference"
    __table_args__ = (
        UniqueConstraint(
            "product_code",
            name="uq_product_reference_product_code",
        ),
        UniqueConstraint(
            "sku",
            name="uq_product_reference_sku",
        ),
        CheckConstraint(
            "case_pack_quantity > 0",
            name="case_pack_quantity_positive",
        ),
        CheckConstraint(
            "shelf_life_days IS NULL OR shelf_life_days >= 0",
            name="shelf_life_days_non_negative",
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="unit_cost_non_negative",
        ),
        CheckConstraint(
            "standard_retail_price >= 0",
            name="retail_price_non_negative",
        ),
        CheckConstraint(
            "gross_margin_rate >= 0 AND gross_margin_rate <= 1",
            name="gross_margin_rate_range",
        ),
        CheckConstraint(
            "vat_rate >= 0 AND vat_rate <= 1",
            name="vat_rate_range",
        ),
        CheckConstraint(
            "reorder_level >= 0",
            name="reorder_level_non_negative",
        ),
        CheckConstraint(
            "safety_stock_quantity >= 0",
            name="safety_stock_non_negative",
        ),
        CheckConstraint(
            "relative_demand_weight > 0",
            name="relative_demand_weight_positive",
        ),
        CheckConstraint(
            "effective_to IS NULL "
            "OR effective_to >= effective_from",
            name="effective_date_order",
        ),
        Index(
            "ix_product_reference_updated_product",
            "updated_at",
            "product_id",
        ),
        Index(
            "ix_product_reference_category_subcategory",
            "category_id",
            "subcategory_id",
        ),
        Index(
            "ix_product_reference_storage_active",
            "storage_type",
            "active_flag",
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    product_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    sku: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    product_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    category_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    subcategory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    subcategory_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    brand_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    brand_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    unit_of_measure: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    package_size: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
    )

    case_pack_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    storage_type: Mapped[StorageType] = mapped_column(
        SqlEnum(
            StorageType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="product_storage_type",
        ),
        nullable=False,
    )

    shelf_life_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    standard_retail_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    gross_margin_rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    safety_stock_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    demand_tier: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    relative_demand_weight: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
    )

    country_of_origin: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )

    origin_group: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    perishable_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    age_restricted_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    active_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    effective_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    effective_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    source_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    synchronised_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class DistributionCentreReference(AuditMixin, Base):
    """
    Read-only distribution-centre reference copied from the SQL system.
    """

    __tablename__ = "distribution_centre_reference"
    __table_args__ = (
        UniqueConstraint(
            "distribution_centre_code",
            name=(
                "uq_distribution_centre_reference_"
                "distribution_centre_code"
            ),
        ),
        CheckConstraint(
            "daily_receiving_capacity_cases > 0",
            name="daily_receiving_capacity_positive",
        ),
        CheckConstraint(
            "daily_dispatch_capacity_cases > 0",
            name="daily_dispatch_capacity_positive",
        ),
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="latitude_range",
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="longitude_range",
        ),
        Index(
            "ix_distribution_centre_reference_updated_id",
            "updated_at",
            "distribution_centre_id",
        ),
        Index(
            "ix_distribution_centre_reference_region",
            "region_id",
        ),
        Index(
            "ix_distribution_centre_reference_active",
            "active_flag",
        ),
    )

    distribution_centre_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )

    distribution_centre_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    distribution_centre_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    region_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    region_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    location_area: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    postcode_area: Mapped[str] = mapped_column(
        String(12),
        nullable=False,
    )

    latitude: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    longitude: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    supports_ambient: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    supports_chilled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    supports_frozen: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    daily_receiving_capacity_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    daily_dispatch_capacity_cases: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    opened_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    active_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    source_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    synchronised_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )