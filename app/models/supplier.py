"""Supplier persistence models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin, utc_now
from app.models.enums import (
    CurrencyCode,
    SupplierRiskRating,
    SupplierStatus,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class Supplier(AuditMixin, Base):
    """Operational supplier master record."""

    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint(
            "supplier_code",
            name="uq_suppliers_supplier_code",
        ),
        UniqueConstraint(
            "contact_email",
            name="uq_suppliers_contact_email",
        ),
        CheckConstraint(
            "standard_lead_time_days >= 0",
            name="standard_lead_time_non_negative",
        ),
        CheckConstraint(
            "minimum_order_value >= 0",
            name="minimum_order_value_non_negative",
        ),
        CheckConstraint(
            "payment_terms_days >= 0",
            name="payment_terms_non_negative",
        ),
        CheckConstraint(
            "target_otif_rate >= 0 "
            "AND target_otif_rate <= 1",
            name="target_otif_rate_range",
        ),
        CheckConstraint(
            "target_quality_acceptance_rate >= 0 "
            "AND target_quality_acceptance_rate <= 1",
            name="target_quality_acceptance_rate_range",
        ),
        CheckConstraint(
            "effective_to IS NULL "
            "OR effective_to >= effective_from",
            name="effective_date_order",
        ),
        Index(
            "ix_suppliers_updated_at_supplier_id",
            "updated_at",
            "supplier_id",
        ),
        Index(
            "ix_suppliers_status_active",
            "supplier_status",
            "active_flag",
        ),
        Index(
            "ix_suppliers_country_code",
            "country_code",
        ),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    supplier_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    supplier_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    legal_name: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    supplier_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    category_codes: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    country_code: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )

    origin_group: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    default_currency_code: Mapped[CurrencyCode] = mapped_column(
        SqlEnum(
            CurrencyCode,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="currency_code",
        ),
        nullable=False,
        default=CurrencyCode.GBP,
    )

    standard_lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    minimum_order_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
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

    risk_rating: Mapped[SupplierRiskRating] = mapped_column(
        SqlEnum(
            SupplierRiskRating,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="supplier_risk_rating",
        ),
        nullable=False,
    )

    supplier_status: Mapped[SupplierStatus] = mapped_column(
        SqlEnum(
            SupplierStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="supplier_status",
        ),
        nullable=False,
    )

    active_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    payment_terms_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    incoterm: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    target_otif_rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    target_quality_acceptance_rate: Mapped[Decimal] = (
        mapped_column(
            Numeric(9, 6),
            nullable=False,
        )
    )

    contact_email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    effective_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    effective_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    status_history: Mapped[list["SupplierStatusHistory"]] = (
        relationship(
            back_populates="supplier",
            cascade="all, delete-orphan",
            passive_deletes=True,
        )
    )


class SupplierStatusHistory(TimestampMixin, Base):
    """Immutable history of supplier status changes."""

    __tablename__ = "supplier_status_history"
    __table_args__ = (
        CheckConstraint(
            "previous_status IS NULL "
            "OR previous_status <> new_status",
            name="status_must_change",
        ),
        Index(
            "ix_supplier_status_history_supplier_occurred",
            "supplier_id",
            "occurred_at",
        ),
        Index(
            "ix_supplier_status_history_updated_id",
            "updated_at",
            "supplier_status_history_id",
        ),
    )

    supplier_status_history_id: Mapped[uuid.UUID] = (
        mapped_column(
            Uuid(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "suppliers.supplier_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    previous_status: Mapped[SupplierStatus | None] = (
        mapped_column(
            SqlEnum(
                SupplierStatus,
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
                name="supplier_previous_status",
            ),
            nullable=True,
        )
    )

    new_status: Mapped[SupplierStatus] = mapped_column(
        SqlEnum(
            SupplierStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="supplier_new_status",
        ),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    changed_by: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    supplier: Mapped["Supplier"] = relationship(
        back_populates="status_history",
    )