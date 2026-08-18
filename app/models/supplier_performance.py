"""Supplier performance event and monthly scorecard models."""

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

from app.db.base import AuditMixin, Base
from app.models.enums import (
    PerformanceEventCategory,
    PerformanceEventSeverity,
    PerformanceRating,
    PerformanceRiskIndicator,
)

if TYPE_CHECKING:
    from app.models.purchase_order import PurchaseOrder
    from app.models.shipment import Shipment
    from app.models.supplier import Supplier


class SupplierPerformanceEvent(AuditMixin, Base):
    """Atomic supplier-performance event derived from operations."""

    __tablename__ = "supplier_performance_events"
    __table_args__ = (
        UniqueConstraint(
            "event_number",
            name=(
                "uq_supplier_performance_events_"
                "event_number"
            ),
        ),
        UniqueConstraint(
            "idempotency_key",
            name=(
                "uq_supplier_performance_events_"
                "idempotency_key"
            ),
        ),
        CheckConstraint(
            "performance_month LIKE '____-__'",
            name="performance_month_format",
        ),
        Index(
            "ix_supplier_performance_events_updated_id",
            "updated_at",
            "supplier_performance_event_id",
        ),
        Index(
            "ix_supplier_performance_events_supplier_month",
            "supplier_id",
            "performance_month",
        ),
        Index(
            "ix_supplier_performance_events_category_time",
            "event_category",
            "event_occurred_at",
        ),
        Index(
            "ix_supplier_performance_events_shipment",
            "shipment_id",
        ),
        Index(
            "ix_supplier_performance_events_purchase_order",
            "purchase_order_id",
        ),
        Index(
            "ix_supplier_performance_events_goods_receipt",
            "goods_receipt_id",
        ),
    )

    supplier_performance_event_id: Mapped[uuid.UUID] = (
        mapped_column(
            Uuid(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )
    )

    event_number: Mapped[str] = mapped_column(
        String(40),
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

    event_type: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
    )

    event_category: Mapped[
        PerformanceEventCategory
    ] = mapped_column(
        SqlEnum(
            PerformanceEventCategory,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="performance_event_category",
        ),
        nullable=False,
    )

    severity: Mapped[PerformanceEventSeverity] = mapped_column(
        SqlEnum(
            PerformanceEventSeverity,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="performance_event_severity",
        ),
        nullable=False,
    )

    source_system: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    shipment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "shipments.shipment_id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    shipment_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    purchase_order_id: Mapped[uuid.UUID | None] = (
        mapped_column(
            Uuid(as_uuid=True),
            ForeignKey(
                "purchase_orders.purchase_order_id",
                ondelete="RESTRICT",
            ),
            nullable=True,
        )
    )

    purchase_order_number: Mapped[str | None] = (
        mapped_column(
            String(30),
            nullable=True,
        )
    )

    goods_receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    goods_receipt_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    event_occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    performance_month: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
    )

    metric_name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    metric_actual_value: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6),
        nullable=True,
    )

    metric_target_value: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6),
        nullable=True,
    )

    passed_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    score_impact: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
    )

    event_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    supplier: Mapped["Supplier"] = relationship()

    shipment: Mapped["Shipment | None"] = relationship()

    purchase_order: Mapped[
        "PurchaseOrder | None"
    ] = relationship()


class SupplierPerformanceMonthly(AuditMixin, Base):
    """Calculated monthly supplier-performance scorecard."""

    __tablename__ = "supplier_performance_monthly"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "performance_month",
            name=(
                "uq_supplier_performance_monthly_"
                "supplier_month"
            ),
        ),
        UniqueConstraint(
            "idempotency_key",
            name=(
                "uq_supplier_performance_monthly_"
                "idempotency_key"
            ),
        ),
        CheckConstraint(
            "performance_month LIKE '____-__'",
            name="performance_month_format",
        ),
        CheckConstraint(
            "delivery_count >= 0",
            name="delivery_count_non_negative",
        ),
        CheckConstraint(
            "early_delivery_count >= 0 "
            "AND on_time_delivery_count >= 0 "
            "AND late_delivery_count >= 0",
            name="delivery_status_counts_non_negative",
        ),
        CheckConstraint(
            "early_delivery_count + "
            "on_time_delivery_count + "
            "late_delivery_count = delivery_count",
            name="delivery_status_counts_reconcile",
        ),
        CheckConstraint(
            "evaluated_purchase_order_count >= 0",
            name="evaluated_order_count_non_negative",
        ),
        CheckConstraint(
            "otif_pass_count >= 0 "
            "AND otif_fail_count >= 0 "
            "AND in_full_pass_count >= 0 "
            "AND in_full_fail_count >= 0",
            name="service_level_counts_non_negative",
        ),
        CheckConstraint(
            "otif_pass_count + otif_fail_count "
            "= evaluated_purchase_order_count",
            name="otif_counts_reconcile",
        ),
        CheckConstraint(
            "in_full_pass_count + in_full_fail_count "
            "= evaluated_purchase_order_count",
            name="in_full_counts_reconcile",
        ),
        CheckConstraint(
            "total_received_quantity >= 0 "
            "AND total_accepted_quantity >= 0 "
            "AND total_damaged_quantity >= 0 "
            "AND total_rejected_quantity >= 0",
            name="quality_quantities_non_negative",
        ),
        CheckConstraint(
            "total_received_quantity = "
            "total_accepted_quantity + "
            "total_damaged_quantity + "
            "total_rejected_quantity",
            name="quality_quantities_reconcile",
        ),
        CheckConstraint(
            "temperature_controlled_delivery_count >= 0 "
            "AND temperature_breach_count >= 0",
            name="temperature_counts_non_negative",
        ),
        CheckConstraint(
            "temperature_breach_count "
            "<= temperature_controlled_delivery_count",
            name="temperature_breaches_not_above_deliveries",
        ),
        CheckConstraint(
            "on_time_delivery_rate >= 0 "
            "AND on_time_delivery_rate <= 1",
            name="on_time_delivery_rate_range",
        ),
        CheckConstraint(
            "in_full_rate >= 0 AND in_full_rate <= 1",
            name="in_full_rate_range",
        ),
        CheckConstraint(
            "otif_rate >= 0 AND otif_rate <= 1",
            name="otif_rate_range",
        ),
        CheckConstraint(
            "accepted_quality_rate >= 0 "
            "AND accepted_quality_rate <= 1",
            name="accepted_quality_rate_range",
        ),
        CheckConstraint(
            "damage_rate >= 0 AND damage_rate <= 1",
            name="damage_rate_range",
        ),
        CheckConstraint(
            "rejection_rate >= 0 AND rejection_rate <= 1",
            name="rejection_rate_range",
        ),
        CheckConstraint(
            "temperature_compliance_rate >= 0 "
            "AND temperature_compliance_rate <= 1",
            name="temperature_compliance_rate_range",
        ),
        CheckConstraint(
            "performance_score >= 0 "
            "AND performance_score <= 100",
            name="performance_score_range",
        ),
        Index(
            "ix_supplier_performance_monthly_updated_id",
            "updated_at",
            "supplier_performance_monthly_id",
        ),
        Index(
            "ix_supplier_performance_monthly_month_rating",
            "performance_month",
            "performance_rating",
        ),
        Index(
            "ix_supplier_performance_monthly_risk",
            "risk_indicator",
        ),
    )

    supplier_performance_monthly_id: Mapped[uuid.UUID] = (
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
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    supplier_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    performance_month: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
    )

    delivery_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    early_delivery_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    on_time_delivery_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    late_delivery_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    evaluated_purchase_order_count: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
        )
    )

    otif_pass_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    otif_fail_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    in_full_pass_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    in_full_fail_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    total_received_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3),
        nullable=False,
    )

    total_accepted_quantity: Mapped[Decimal] = mapped_column(
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

    temperature_controlled_delivery_count: Mapped[int] = (
        mapped_column(
            Integer,
            nullable=False,
        )
    )

    temperature_breach_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    on_time_delivery_rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    in_full_rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    otif_rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    accepted_quality_rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    damage_rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    rejection_rate: Mapped[Decimal] = mapped_column(
        Numeric(9, 6),
        nullable=False,
    )

    temperature_compliance_rate: Mapped[Decimal] = (
        mapped_column(
            Numeric(9, 6),
            nullable=False,
        )
    )

    performance_score: Mapped[Decimal] = mapped_column(
        Numeric(9, 4),
        nullable=False,
    )

    performance_rating: Mapped[PerformanceRating] = (
        mapped_column(
            SqlEnum(
                PerformanceRating,
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
                name="supplier_performance_rating",
            ),
            nullable=False,
        )
    )

    risk_indicator: Mapped[PerformanceRiskIndicator] = (
        mapped_column(
            SqlEnum(
                PerformanceRiskIndicator,
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
                name="supplier_performance_risk_indicator",
            ),
            nullable=False,
        )
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    supplier: Mapped["Supplier"] = relationship()