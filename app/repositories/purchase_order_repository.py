"""Database access operations for BritMart purchase orders."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.purchase_order import PurchaseOrder, PurchaseOrderLine
from app.schemas.purchase_order import PurchaseOrderFilterParameters


class PurchaseOrderRepository:
    """Database access for purchase-order headers and lines."""

    def __init__(self, database_session: Session) -> None:
        self.database_session = database_session

    @staticmethod
    def _apply_filters(
        statement: Select[tuple[PurchaseOrder]],
        parameters: PurchaseOrderFilterParameters,
    ) -> Select[tuple[PurchaseOrder]]:
        """Apply business and incremental-extraction filters."""

        if parameters.purchase_order_status is not None:
            statement = statement.where(
                PurchaseOrder.purchase_order_status
                == parameters.purchase_order_status.value
            )

        if parameters.order_type is not None:
            statement = statement.where(
                PurchaseOrder.order_type == parameters.order_type.value
            )

        if parameters.supplier_id is not None:
            statement = statement.where(
                PurchaseOrder.supplier_id == parameters.supplier_id
            )

        if parameters.distribution_centre_id is not None:
            statement = statement.where(
                PurchaseOrder.distribution_centre_id
                == parameters.distribution_centre_id
            )

        if parameters.order_date_from is not None:
            statement = statement.where(
                PurchaseOrder.order_date >= parameters.order_date_from
            )

        if parameters.order_date_to is not None:
            statement = statement.where(
                PurchaseOrder.order_date <= parameters.order_date_to
            )

        if parameters.updated_since is not None:
            statement = statement.where(
                PurchaseOrder.updated_at >= parameters.updated_since
            )

        if parameters.updated_before is not None:
            statement = statement.where(
                PurchaseOrder.updated_at < parameters.updated_before
            )

        return statement

    def list_purchase_orders(
        self,
        parameters: PurchaseOrderFilterParameters,
    ) -> tuple[list[PurchaseOrder], int]:
        """Return one deterministic purchase-order page."""

        filtered_statement = self._apply_filters(
            select(PurchaseOrder),
            parameters,
        )

        count_statement = select(func.count()).select_from(
            filtered_statement.order_by(None).subquery()
        )
        total_records = int(
            self.database_session.scalar(count_statement) or 0
        )

        offset = (parameters.page - 1) * parameters.page_size

        page_statement = (
            filtered_statement
            .order_by(
                PurchaseOrder.updated_at.asc(),
                PurchaseOrder.purchase_order_id.asc(),
            )
            .offset(offset)
            .limit(parameters.page_size)
        )

        purchase_orders = list(
            self.database_session.scalars(page_statement).all()
        )

        return purchase_orders, total_records

    def get_by_id(
        self,
        purchase_order_id: UUID,
    ) -> PurchaseOrder | None:
        """Return a purchase order by technical identifier."""

        return self.database_session.scalar(
            select(PurchaseOrder).where(
                PurchaseOrder.purchase_order_id == purchase_order_id
            )
        )

    def get_by_number(
        self,
        purchase_order_number: str,
    ) -> PurchaseOrder | None:
        """Return a purchase order by business number."""

        return self.database_session.scalar(
            select(PurchaseOrder).where(
                PurchaseOrder.purchase_order_number
                == purchase_order_number.upper()
            )
        )

    def list_lines(
        self,
        purchase_order_id: UUID,
    ) -> list[PurchaseOrderLine]:
        """Return all lines for a purchase order in line-number order."""

        statement = (
            select(PurchaseOrderLine)
            .where(
                PurchaseOrderLine.purchase_order_id
                == purchase_order_id
            )
            .order_by(PurchaseOrderLine.line_number.asc())
        )

        return list(
            self.database_session.scalars(statement).all()
        )