"""Purchase-order header and line persistence models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base
from app.models.enums import (
    CurrencyCode,
    PurchaseOrderStatus,
    PurchaseOrderType,
)

if TYPE_CHECKING:
    from app.models.reference import (
        DistributionCentreReference,
        ProductReference,
    )
    from app.models.supplier import Supplier
    from app.models.supplier_product import SupplierProduct


class PurchaseOrder(AuditMixin, Base):
    """Purchase-order header raised against one supplier."""

    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint(
            "purchase_order_number",
            name="uq_purchase_orders_purchase_order_number",
        ),
        CheckConstraint(
            "required_delivery_date >= order_date",
            name="required_delivery_not_before_order",
        ),
        CheckConstraint(
            "total_net_amount >= 0",
            name="total_net_amount_non_negative",
        ),
        CheckConstraint(
            "total_vat_amount >= 0",
            name="total_vat_amount_non_negative",
        ),
        CheckConstraint(
            "total_gross_amount >= 0",
            name="total_gross_amount_non_negative",
        ),
        CheckConstraint(
            "total_value_gbp >= 0",
            name="total_value_gbp_non_negative",
        ),
        CheckConstraint(
            "ABS(total_gross_amount - "
    "(total_net_amount + total_vat_amount)) <= 0.01",
    name="header_amounts_reconcile",
        ),
        CheckConstraint(
            "("
            "purchase_order_status = 'CANCELLED' "
            "AND cancellation_reason IS NOT NULL"
            ") OR ("
            "purchase_order_status <> 'CANCELLED'"
            ")",
            name="cancelled_order_requires_reason",
        ),
        Index(
            "ix_purchase_orders_updated_id",
            "updated_at",
            "purchase_order_id",
        ),
        Index(
            "ix_purchase_orders_supplier_status",
            "supplier_id",
            "purchase_order_status",
        ),
        Index(
            "ix_purchase_orders_dc_delivery_date",
            "distribution_centre_id",
            "required_delivery_date",
        ),
        Index(
            "ix_purchase_orders_order_date",
            "order_date",
        ),
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    purchase_order_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
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

    distribution_centre_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "distribution_centre_reference."
            "distribution_centre_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    distribution_centre_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    order_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    required_delivery_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    order_type: Mapped[PurchaseOrderType] = mapped_column(
        SqlEnum(
            PurchaseOrderType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="purchase_order_type",
        ),
        nullable=False,
    )

    purchase_order_status: Mapped[PurchaseOrderStatus] = (
        mapped_column(
            SqlEnum(
                PurchaseOrderStatus,
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
                name="purchase_order_status",
            ),
            nullable=False,
        )
    )

    currency_code: Mapped[CurrencyCode] = mapped_column(
        SqlEnum(
            CurrencyCode,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="purchase_order_currency_code",
        ),
        nullable=False,
    )

    total_net_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    total_vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    total_gross_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    total_value_gbp: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    buyer_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    approval_role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_by: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    updated_by: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    supplier: Mapped["Supplier"] = relationship()

    distribution_centre: Mapped[
        "DistributionCentreReference"
    ] = relationship()

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PurchaseOrderLine.line_number",
    )


class PurchaseOrderLine(AuditMixin, Base):
    """Individual product line belonging to a purchase order."""

    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        UniqueConstraint(
            "purchase_order_id",
            "line_number",
            name="uq_purchase_order_lines_order_line",
        ),
        UniqueConstraint(
            "purchase_order_id",
            "product_id",
            name="uq_purchase_order_lines_order_product",
        ),
        CheckConstraint(
            "line_number > 0",
            name="line_number_positive",
        ),
        CheckConstraint(
            "ordered_quantity > 0",
            name="ordered_quantity_positive",
        ),
        CheckConstraint(
            "order_multiple > 0",
            name="order_multiple_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="unit_price_non_negative",
        ),
        CheckConstraint(
            "net_amount >= 0",
            name="net_amount_non_negative",
        ),
        CheckConstraint(
            "vat_rate >= 0 AND vat_rate <= 1",
            name="vat_rate_range",
        ),
        CheckConstraint(
            "vat_amount >= 0",
            name="vat_amount_non_negative",
        ),
        CheckConstraint(
            "gross_amount >= 0",
            name="gross_amount_non_negative",
        ),
        CheckConstraint(
           "ABS(gross_amount - (net_amount + vat_amount)) <= 0.01",
    name="line_amounts_reconcile",
        ),
        Index(
            "ix_purchase_order_lines_updated_id",
            "updated_at",
            "purchase_order_line_id",
        ),
        Index(
            "ix_purchase_order_lines_order",
            "purchase_order_id",
        ),
        Index(
            "ix_purchase_order_lines_product",
            "product_id",
        ),
        Index(
            "ix_purchase_order_lines_supplier_product",
            "supplier_product_id",
        ),
    )

    purchase_order_line_id: Mapped[uuid.UUID] = (
        mapped_column(
            Uuid(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "purchase_orders.purchase_order_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    purchase_order_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    supplier_product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "supplier_products.supplier_product_id",
            ondelete="RESTRICT",
        ),
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

    ordered_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    unit_of_measure: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    order_multiple: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    currency_code: Mapped[CurrencyCode] = mapped_column(
        SqlEnum(
            CurrencyCode,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="purchase_order_line_currency_code",
        ),
        nullable=False,
    )

    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    gross_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship(
        back_populates="lines",
    )

    supplier_product: Mapped["SupplierProduct"] = relationship()

    product: Mapped["ProductReference"] = relationship()