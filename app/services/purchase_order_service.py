"""Business services for BritMart purchase orders."""

from __future__ import annotations

from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.purchase_order_repository import (
    PurchaseOrderRepository,
)
from app.schemas.common import PaginationMetadata
from app.schemas.purchase_order import (
    PurchaseOrderDetailResponse,
    PurchaseOrderFilterParameters,
    PurchaseOrderLineResponse,
    PurchaseOrderListResponse,
    PurchaseOrderSummaryResponse,
)


class PurchaseOrderService:
    """Coordinate purchase-order retrieval and response construction."""

    def __init__(self, database_session: Session) -> None:
        self.repository = PurchaseOrderRepository(database_session)

    def list_purchase_orders(
        self,
        parameters: PurchaseOrderFilterParameters,
    ) -> PurchaseOrderListResponse:
        """Return a filtered, paginated purchase-order collection."""

        purchase_orders, total_records = (
            self.repository.list_purchase_orders(parameters)
        )

        total_pages = (
            ceil(total_records / parameters.page_size)
            if total_records
            else 0
        )

        return PurchaseOrderListResponse(
            items=[
                PurchaseOrderSummaryResponse.model_validate(order)
                for order in purchase_orders
            ],
            pagination=PaginationMetadata(
                page=parameters.page,
                page_size=parameters.page_size,
                total_records=total_records,
                total_pages=total_pages,
                has_next=parameters.page < total_pages,
                has_previous=(
                    parameters.page > 1 and total_pages > 0
                ),
            ),
        )

    def _build_detail(
        self,
        purchase_order_id: UUID,
    ) -> PurchaseOrderDetailResponse:
        """Build a purchase-order header-and-lines response."""

        purchase_order = self.repository.get_by_id(
            purchase_order_id
        )

        if purchase_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PURCHASE_ORDER_NOT_FOUND",
                    "message": (
                        f"Purchase order '{purchase_order_id}' "
                        "does not exist."
                    ),
                    "field": "purchase_order_id",
                },
            )

        lines = self.repository.list_lines(purchase_order_id)

        header = PurchaseOrderDetailResponse.model_validate(
            {
                **{
                    column.name: getattr(purchase_order, column.name)
                    for column in purchase_order.__table__.columns
                },
                "lines": [
                    PurchaseOrderLineResponse.model_validate(line)
                    for line in lines
                ],
            }
        )

        return header

    def get_purchase_order(
        self,
        purchase_order_id: UUID,
    ) -> PurchaseOrderDetailResponse:
        """Return a purchase order by technical identifier."""

        return self._build_detail(purchase_order_id)

    def get_purchase_order_by_number(
        self,
        purchase_order_number: str,
    ) -> PurchaseOrderDetailResponse:
        """Return a purchase order by operational number."""

        normalised_number = purchase_order_number.strip().upper()
        purchase_order = self.repository.get_by_number(
            normalised_number
        )

        if purchase_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PURCHASE_ORDER_NOT_FOUND",
                    "message": (
                        f"Purchase order number "
                        f"'{normalised_number}' does not exist."
                    ),
                    "field": "purchase_order_number",
                },
            )

        return self._build_detail(
            purchase_order.purchase_order_id
        )