"""Supplier-product commercial agreement model."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base
from app.models.enums import (
    AgreementRole,
    AgreementStatus,
    CurrencyCode,
)

if TYPE_CHECKING:
    from app.models.reference import ProductReference
    from app.models.supplier import Supplier


class SupplierProduct(AuditMixin, Base):
    """Commercial agreement between one supplier and one product."""

    __tablename__ = "supplier_products"
    __table_args__ = (
        UniqueConstraint(
            "supplier_product_code",
            name="uq_supplier_products_supplier_product_code",
        ),
        UniqueConstraint(
            "supplier_id",
            "product_id",
            name="uq_supplier_products_supplier_product",
        ),
        CheckConstraint(
            "base_unit_cost_gbp >= 0",
            name="base_unit_cost_gbp_non_negative",
        ),
        CheckConstraint(
            "agreed_unit_cost >= 0",
            name="agreed_unit_cost_non_negative",
        ),
        CheckConstraint(
            "gbp_value_per_currency_unit > 0",
            name="currency_conversion_rate_positive",
        ),
        CheckConstraint(
            "minimum_order_quantity > 0",
            name="minimum_order_quantity_positive",
        ),
        CheckConstraint(
            "order_multiple > 0",
            name="order_multiple_positive",
        ),
        CheckConstraint(
            "agreed_lead_time_days >= 0",
            name="agreed_lead_time_non_negative",
        ),
        CheckConstraint(
            "minimum_remaining_shelf_life_days >= 0",
            name="minimum_shelf_life_non_negative",
        ),
        CheckConstraint(
            "effective_to IS NULL "
            "OR effective_to >= effective_from",
            name="effective_date_order",
        ),
        CheckConstraint(
            "("
            "agreement_role = 'PRIMARY' "
            "AND is_primary_supplier"
            ") OR ("
            "agreement_role = 'SECONDARY' "
            "AND NOT is_primary_supplier"
            ")",
            name="agreement_role_primary_flag_consistent",
        ),
        Index(
            "ix_supplier_products_updated_id",
            "updated_at",
            "supplier_product_id",
        ),
        Index(
            "ix_supplier_products_supplier_status",
            "supplier_id",
            "agreement_status",
        ),
        Index(
            "ix_supplier_products_product_status",
            "product_id",
            "agreement_status",
        ),
        Index(
            "ix_supplier_products_primary_product",
            "product_id",
            "is_primary_supplier",
        ),
    )

    supplier_product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "suppliers.supplier_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    supplier_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "product_reference.product_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    product_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    sku: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    supplier_product_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    agreement_role: Mapped[AgreementRole] = mapped_column(
        SqlEnum(
            AgreementRole,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="agreement_role",
        ),
        nullable=False,
    )

    is_primary_supplier: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    agreement_status: Mapped[AgreementStatus] = mapped_column(
        SqlEnum(
            AgreementStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="agreement_status",
        ),
        nullable=False,
    )

    agreement_currency_code: Mapped[CurrencyCode] = mapped_column(
        SqlEnum(
            CurrencyCode,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="agreement_currency_code",
        ),
        nullable=False,
    )

    base_unit_cost_gbp: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    agreed_unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    gbp_value_per_currency_unit: Mapped[Decimal] = mapped_column(
        Numeric(18, 8),
        nullable=False,
    )

    minimum_order_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    order_multiple: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    agreed_lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    minimum_remaining_shelf_life_days: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
            default=0,
        )
    )

    effective_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    effective_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    supplier: Mapped["Supplier"] = relationship()

    product: Mapped["ProductReference"] = relationship()