"""Supplier shipment, shipment-line and status-history models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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

from app.db.base import AuditMixin, Base, utc_now
from app.models.enums import (
    DeliveryPerformance,
    ShipmentStatus,
    StorageType,
)

if TYPE_CHECKING:
    from app.models.purchase_order import (
        PurchaseOrder,
        PurchaseOrderLine,
    )
    from app.models.reference import (
        DistributionCentreReference,
        ProductReference,
    )
    from app.models.supplier import Supplier
    from app.models.supplier_product import SupplierProduct


class Shipment(AuditMixin, Base):
    """Supplier shipment against one purchase order."""

    __tablename__ = "shipments"
    __table_args__ = (
        UniqueConstraint(
            "shipment_number",
            name="uq_shipments_shipment_number",
        ),
        UniqueConstraint(
            "supplier_shipment_reference",
            name=(
                "uq_shipments_supplier_shipment_reference"
            ),
        ),
        CheckConstraint(
            "expected_delivery_at >= planned_dispatch_at",
            name="expected_delivery_after_planned_dispatch",
        ),
        CheckConstraint(
            "actual_dispatch_at IS NULL "
            "OR actual_dispatch_at >= planned_dispatch_at",
            name="actual_dispatch_after_planned_dispatch",
        ),
        CheckConstraint(
            "actual_delivery_at IS NULL "
            "OR actual_dispatch_at IS NULL "
            "OR actual_delivery_at >= actual_dispatch_at",
            name="actual_delivery_after_dispatch",
        ),
        CheckConstraint(
            "total_planned_quantity >= 0",
            name="total_planned_quantity_non_negative",
        ),
        CheckConstraint(
            "total_shipped_quantity >= 0",
            name="total_shipped_quantity_non_negative",
        ),
        CheckConstraint(
            "total_received_quantity >= 0",
            name="total_received_quantity_non_negative",
        ),
        CheckConstraint(
            "total_damaged_quantity >= 0",
            name="total_damaged_quantity_non_negative",
        ),
        CheckConstraint(
            "total_rejected_quantity >= 0",
            name="total_rejected_quantity_non_negative",
        ),
        CheckConstraint(
            "total_accepted_quantity >= 0",
            name="total_accepted_quantity_non_negative",
        ),
        CheckConstraint(
            "total_shipped_quantity <= total_planned_quantity",
            name="shipped_not_above_planned",
        ),
        CheckConstraint(
            "total_received_quantity <= total_shipped_quantity",
            name="received_not_above_shipped",
        ),
        CheckConstraint(
            "total_received_quantity = "
            "total_accepted_quantity + "
            "total_damaged_quantity + "
            "total_rejected_quantity",
            name="received_quantity_reconciles",
        ),
        CheckConstraint(
            "minimum_recorded_temperature_celsius IS NULL "
            "OR maximum_recorded_temperature_celsius IS NULL "
            "OR minimum_recorded_temperature_celsius "
            "<= maximum_recorded_temperature_celsius",
            name="temperature_range_order",
        ),
        CheckConstraint(
            "("
            "NOT temperature_controlled_flag "
            "AND minimum_recorded_temperature_celsius IS NULL "
            "AND maximum_recorded_temperature_celsius IS NULL "
            "AND NOT temperature_breach_flag"
            ") OR ("
            "temperature_controlled_flag"
            ")",
            name="temperature_fields_consistent",
        ),
        CheckConstraint(
            "("
            "shipment_status = 'CANCELLED' "
            "AND cancellation_reason IS NOT NULL"
            ") OR ("
            "shipment_status <> 'CANCELLED'"
            ")",
            name="cancelled_shipment_requires_reason",
        ),
        Index(
            "ix_shipments_updated_id",
            "updated_at",
            "shipment_id",
        ),
        Index(
            "ix_shipments_purchase_order",
            "purchase_order_id",
        ),
        Index(
            "ix_shipments_supplier_status",
            "supplier_id",
            "shipment_status",
        ),
        Index(
            "ix_shipments_dc_expected_delivery",
            "distribution_centre_id",
            "expected_delivery_at",
        ),
        Index(
            "ix_shipments_actual_delivery",
            "actual_delivery_at",
        ),
    )

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    shipment_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    supplier_shipment_reference: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "purchase_orders.purchase_order_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
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

    carrier_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    carrier_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    vehicle_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    shipment_status: Mapped[ShipmentStatus] = mapped_column(
        SqlEnum(
            ShipmentStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="shipment_status",
        ),
        nullable=False,
    )

    delivery_performance_status: Mapped[
        DeliveryPerformance
    ] = mapped_column(
        SqlEnum(
            DeliveryPerformance,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="delivery_performance_status",
        ),
        nullable=False,
    )

    planned_dispatch_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    actual_dispatch_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    expected_delivery_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    actual_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    total_planned_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    total_shipped_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    total_received_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    total_damaged_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    total_rejected_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    total_accepted_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    temperature_controlled_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    minimum_recorded_temperature_celsius: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(8, 3),
        nullable=True,
    )

    maximum_recorded_temperature_celsius: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(8, 3),
        nullable=True,
    )

    temperature_breach_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship()

    supplier: Mapped["Supplier"] = relationship()

    distribution_centre: Mapped[
        "DistributionCentreReference"
    ] = relationship()

    lines: Mapped[list["ShipmentLine"]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ShipmentLine.line_number",
    )

    status_history: Mapped[list["ShipmentStatusHistory"]] = (
        relationship(
            back_populates="shipment",
            cascade="all, delete-orphan",
            passive_deletes=True,
            order_by="ShipmentStatusHistory.sequence_number",
        )
    )


class ShipmentLine(AuditMixin, Base):
    """Product quantity allocated to one supplier shipment."""

    __tablename__ = "shipment_lines"
    __table_args__ = (
        UniqueConstraint(
            "shipment_id",
            "purchase_order_line_id",
            name="uq_shipment_lines_shipment_order_line",
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
            "planned_quantity > 0",
            name="planned_quantity_positive",
        ),
        CheckConstraint(
            "shipped_quantity >= 0",
            name="shipped_quantity_non_negative",
        ),
        CheckConstraint(
            "received_quantity >= 0",
            name="received_quantity_non_negative",
        ),
        CheckConstraint(
            "damaged_quantity >= 0",
            name="damaged_quantity_non_negative",
        ),
        CheckConstraint(
            "rejected_quantity >= 0",
            name="rejected_quantity_non_negative",
        ),
        CheckConstraint(
            "accepted_quantity >= 0",
            name="accepted_quantity_non_negative",
        ),
        CheckConstraint(
            "planned_quantity <= ordered_quantity",
            name="planned_not_above_ordered",
        ),
        CheckConstraint(
            "shipped_quantity <= planned_quantity",
            name="shipped_not_above_planned",
        ),
        CheckConstraint(
            "received_quantity <= shipped_quantity",
            name="received_not_above_shipped",
        ),
        CheckConstraint(
            "received_quantity = "
            "accepted_quantity + "
            "damaged_quantity + "
            "rejected_quantity",
            name="received_quantity_reconciles",
        ),
        Index(
            "ix_shipment_lines_updated_id",
            "updated_at",
            "shipment_line_id",
        ),
        Index(
            "ix_shipment_lines_shipment",
            "shipment_id",
        ),
        Index(
            "ix_shipment_lines_order_line",
            "purchase_order_line_id",
        ),
        Index(
            "ix_shipment_lines_product",
            "product_id",
        ),
    )

    shipment_line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "shipments.shipment_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    shipment_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "purchase_orders.purchase_order_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    purchase_order_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    purchase_order_line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "purchase_order_lines.purchase_order_line_id",
            ondelete="RESTRICT",
        ),
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

    storage_type: Mapped[StorageType] = mapped_column(
        SqlEnum(
            StorageType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="shipment_line_storage_type",
        ),
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

    ordered_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    planned_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    shipped_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    received_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    damaged_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    rejected_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    accepted_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    shipment: Mapped["Shipment"] = relationship(
        back_populates="lines",
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship()

    purchase_order_line: Mapped[
        "PurchaseOrderLine"
    ] = relationship()

    supplier_product: Mapped["SupplierProduct"] = relationship()

    product: Mapped["ProductReference"] = relationship()


class ShipmentStatusHistory(Base):
    """Immutable ordered history of shipment status changes."""

    __tablename__ = "shipment_status_history"
    __table_args__ = (
        UniqueConstraint(
            "shipment_id",
            "sequence_number",
            name=(
                "uq_shipment_status_history_"
                "shipment_sequence"
            ),
        ),
        CheckConstraint(
            "sequence_number > 0",
            name="sequence_number_positive",
        ),
        CheckConstraint(
            "previous_status IS NULL "
            "OR previous_status <> new_status",
            name="status_must_change",
        ),
        Index(
            "ix_shipment_status_history_shipment_changed",
            "shipment_id",
            "status_changed_at",
        ),
        Index(
            "ix_shipment_status_history_created_id",
            "created_at",
            "shipment_status_history_id",
        ),
    )

    shipment_status_history_id: Mapped[uuid.UUID] = (
        mapped_column(
            Uuid(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )
    )

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "shipments.shipment_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    shipment_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    previous_status: Mapped[ShipmentStatus | None] = (
        mapped_column(
            SqlEnum(
                ShipmentStatus,
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
                name="shipment_previous_status",
            ),
            nullable=True,
        )
    )

    new_status: Mapped[ShipmentStatus] = mapped_column(
        SqlEnum(
            ShipmentStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="shipment_new_status",
        ),
        nullable=False,
    )

    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    changed_by: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    status_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    shipment: Mapped["Shipment"] = relationship(
        back_populates="status_history",
    )