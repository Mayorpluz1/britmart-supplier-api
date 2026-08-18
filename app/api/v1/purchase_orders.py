"""Version 1 purchase-order endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.database import DatabaseSession
from app.dependencies.security import verify_api_key
from app.schemas.common import ErrorResponse
from app.schemas.purchase_order import (
    PurchaseOrderDetailResponse,
    PurchaseOrderFilterParameters,
    PurchaseOrderListResponse,
)
from app.services.purchase_order_service import PurchaseOrderService


router = APIRouter(
    prefix="/purchase-orders",
    tags=["Purchase Orders"],
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "",
    response_model=PurchaseOrderListResponse,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="List purchase orders",
)
def list_purchase_orders(
    database_session: DatabaseSession,
    parameters: Annotated[
        PurchaseOrderFilterParameters,
        Query(),
    ],
) -> PurchaseOrderListResponse:
    """Return filtered purchase orders for operational use or Fabric."""

    return PurchaseOrderService(
        database_session
    ).list_purchase_orders(parameters)


@router.get(
    "/by-number/{purchase_order_number}",
    response_model=PurchaseOrderDetailResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Get purchase order by number",
)
def get_purchase_order_by_number(
    database_session: DatabaseSession,
    purchase_order_number: Annotated[
        str,
        Path(min_length=1, max_length=40),
    ],
) -> PurchaseOrderDetailResponse:
    """Return one purchase order and all its lines."""

    return PurchaseOrderService(
        database_session
    ).get_purchase_order_by_number(purchase_order_number)


@router.get(
    "/{purchase_order_id}",
    response_model=PurchaseOrderDetailResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Get purchase order by identifier",
)
def get_purchase_order(
    database_session: DatabaseSession,
    purchase_order_id: Annotated[UUID, Path()],
) -> PurchaseOrderDetailResponse:
    """Return one purchase order and all its lines."""

    return PurchaseOrderService(
        database_session
    ).get_purchase_order(purchase_order_id)