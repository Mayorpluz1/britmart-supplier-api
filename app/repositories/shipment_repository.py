"""Database access operations for BritMart shipments."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.shipment import (
    Shipment,
    ShipmentLine,
    ShipmentStatusHistory,
)
from app.schemas.shipment import ShipmentFilterParameters


class ShipmentRepository:
    """Database access for shipment headers, lines and history."""

    def __init__(self, database_session: Session) -> None:
        self.database_session = database_session

    @staticmethod
    def _apply_filters(
        statement: Select[tuple[Shipment]],
        parameters: ShipmentFilterParameters,
    ) -> Select[tuple[Shipment]]:
        """Apply shipment filters."""

        filters = {
            Shipment.shipment_status: parameters.shipment_status,
            Shipment.delivery_performance_status:
                parameters.delivery_performance_status,
            Shipment.supplier_id: parameters.supplier_id,
            Shipment.purchase_order_id: parameters.purchase_order_id,
            Shipment.distribution_centre_id:
                parameters.distribution_centre_id,
            Shipment.temperature_controlled_flag:
                parameters.temperature_controlled_flag,
            Shipment.temperature_breach_flag:
                parameters.temperature_breach_flag,
        }

        for column, value in filters.items():
            if value is not None:
                comparable_value = getattr(value, "value", value)
                statement = statement.where(
                    column == comparable_value
                )

        if parameters.updated_since is not None:
            statement = statement.where(
                Shipment.updated_at >= parameters.updated_since
            )

        if parameters.updated_before is not None:
            statement = statement.where(
                Shipment.updated_at < parameters.updated_before
            )

        return statement

    def list_shipments(
        self,
        parameters: ShipmentFilterParameters,
    ) -> tuple[list[Shipment], int]:
        """Return one deterministic shipment page."""

        filtered = self._apply_filters(
            select(Shipment),
            parameters,
        )

        total_records = int(
            self.database_session.scalar(
                select(func.count()).select_from(
                    filtered.order_by(None).subquery()
                )
            )
            or 0
        )

        statement = (
            filtered
            .order_by(
                Shipment.updated_at.asc(),
                Shipment.shipment_id.asc(),
            )
            .offset(
                (parameters.page - 1) * parameters.page_size
            )
            .limit(parameters.page_size)
        )

        return (
            list(self.database_session.scalars(statement).all()),
            total_records,
        )

    def get_by_id(self, shipment_id: UUID) -> Shipment | None:
        """Return a shipment by UUID."""

        return self.database_session.scalar(
            select(Shipment).where(
                Shipment.shipment_id == shipment_id
            )
        )

    def get_by_number(
        self,
        shipment_number: str,
    ) -> Shipment | None:
        """Return a shipment by business number."""

        return self.database_session.scalar(
            select(Shipment).where(
                Shipment.shipment_number
                == shipment_number.upper()
            )
        )

    def list_lines(
        self,
        shipment_id: UUID,
    ) -> list[ShipmentLine]:
        """Return shipment lines."""

        return list(
            self.database_session.scalars(
                select(ShipmentLine)
                .where(ShipmentLine.shipment_id == shipment_id)
                .order_by(ShipmentLine.line_number.asc())
            ).all()
        )

    def list_status_history(
        self,
        shipment_id: UUID,
    ) -> list[ShipmentStatusHistory]:
        """Return ordered shipment lifecycle events."""

        return list(
            self.database_session.scalars(
                select(ShipmentStatusHistory)
                .where(
                    ShipmentStatusHistory.shipment_id
                    == shipment_id
                )
                .order_by(
                    ShipmentStatusHistory.sequence_number.asc()
                )
            ).all()
        )