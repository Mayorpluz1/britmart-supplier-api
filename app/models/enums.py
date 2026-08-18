"""Controlled business values used by BritMart operational models."""

from __future__ import annotations

from enum import StrEnum


class SupplierStatus(StrEnum):
    """Operational lifecycle state of a supplier."""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"


class SupplierRiskRating(StrEnum):
    """Commercial and operational supplier risk."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SupplierType(StrEnum):
    """High-level commercial type of supplier."""

    MANUFACTURER = "MANUFACTURER"
    WHOLESALER = "WHOLESALER"
    DISTRIBUTOR = "DISTRIBUTOR"
    IMPORTER = "IMPORTER"
    PRODUCER = "PRODUCER"
    SERVICE_PROVIDER = "SERVICE_PROVIDER"
    OTHER = "OTHER"


class StorageType(StrEnum):
    """Required storage and handling environment."""

    AMBIENT = "AMBIENT"
    CHILLED = "CHILLED"
    FROZEN = "FROZEN"


class AgreementRole(StrEnum):
    """Supplier role for an agreed product."""

    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"


class AgreementStatus(StrEnum):
    """Lifecycle state of a supplier-product agreement."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"


class PurchaseOrderStatus(StrEnum):
    """Operational purchase-order lifecycle state."""

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_SHIPPED = "PARTIALLY_SHIPPED"
    DISPATCHED = "DISPATCHED"
    SHIPPED = "SHIPPED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class PurchaseOrderType(StrEnum):
    """Business reason for raising a purchase order."""

    STANDARD_REPLENISHMENT = "STANDARD_REPLENISHMENT"
    EMERGENCY_REPLENISHMENT = "EMERGENCY_REPLENISHMENT"
    PROMOTIONAL = "PROMOTIONAL"
    NEW_PRODUCT_LAUNCH = "NEW_PRODUCT_LAUNCH"
    SEASONAL = "SEASONAL"


class ShipmentStatus(StrEnum):
    """Supplier shipment lifecycle state."""

    PLANNED = "PLANNED"
    READY_FOR_DISPATCH = "READY_FOR_DISPATCH"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    DELAYED = "DELAYED"
    ARRIVED = "ARRIVED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class DeliveryPerformance(StrEnum):
    """Delivery timing classification."""

    EARLY = "EARLY"
    ON_TIME = "ON_TIME"
    LATE = "LATE"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReceiptStatus(StrEnum):
    """Warehouse goods-receipt processing state."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    PARTIALLY_ACCEPTED = "PARTIALLY_ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class QualityDisposition(StrEnum):
    """Warehouse disposition of received stock."""

    AVAILABLE = "AVAILABLE"
    QUARANTINE = "QUARANTINE"
    REJECTED = "REJECTED"


class InventoryMovementType(StrEnum):
    """Stock effect produced by warehouse receiving."""

    RECEIPT_AVAILABLE = "RECEIPT_AVAILABLE"
    RECEIPT_QUARANTINE = "RECEIPT_QUARANTINE"
    RECEIPT_REJECTED = "RECEIPT_REJECTED"
    QUALITY_RELEASE = "QUALITY_RELEASE"
    QUALITY_REJECTION = "QUALITY_REJECTION"
    ADJUSTMENT_INCREASE = "ADJUSTMENT_INCREASE"
    ADJUSTMENT_DECREASE = "ADJUSTMENT_DECREASE"


class PerformanceEventCategory(StrEnum):
    """High-level supplier performance event category."""

    DELIVERY = "DELIVERY"
    QUALITY = "QUALITY"
    COLD_CHAIN = "COLD_CHAIN"
    SERVICE_LEVEL = "SERVICE_LEVEL"
    IN_FULL = "IN_FULL"
    OTIF = "OTIF"
    TEMPERATURE = "TEMPERATURE"
    COMPLIANCE = "COMPLIANCE"


class PerformanceEventSeverity(StrEnum):
    """Business impact of a supplier performance event."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    INFORMATIONAL = "INFORMATIONAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PerformanceRating(StrEnum):
    """Monthly supplier performance rating."""

    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    WATCH = "WATCH"
    HIGH_RISK = "HIGH_RISK"
    ACCEPTABLE = "ACCEPTABLE"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    POOR = "POOR"


class PerformanceRiskIndicator(StrEnum):
    """Monthly operational risk derived from supplier performance."""

    NORMAL = "NORMAL"
    WATCH = "WATCH"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CurrencyCode(StrEnum):
    """Supported procurement currencies."""

    GBP = "GBP"
    EUR = "EUR"
    USD = "USD"
    AUD = "AUD"


class SourceSystem(StrEnum):
    """Authoritative BritMart operational source."""

    SUPPLIER_API = "SUPPLIER_API"
    SQL_OPERATIONAL_SYSTEM = "SQL_OPERATIONAL_SYSTEM"
    FABRIC = "FABRIC"