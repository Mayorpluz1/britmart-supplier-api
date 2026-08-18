"""Version 1 shipment endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from app.dependencies.database import DatabaseSession
from app.dependencies.security import verify_api_key
from app.schemas.common import ErrorResponse
from app.schemas.shipment import (
    ShipmentDetailResponse,
    ShipmentFilterParameters,
    ShipmentListResponse,
)
from app.services.shipment_service import ShipmentService


router = APIRouter(
    prefix="/shipments",
    tags=["Shipments"],
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "",
    response_model=ShipmentListResponse,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="List supplier shipments",
)
def list_shipments(
    database_session: DatabaseSession,
    parameters: Annotated[ShipmentFilterParameters, Query()],
) -> ShipmentListResponse:
    """Return paginated shipments for operations or Fabric."""

    return ShipmentService(database_session).list_shipments(
        parameters
    )


@router.get(
    "/by-number/{shipment_number}",
    response_model=ShipmentDetailResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Get shipment by number",
)
def get_shipment_by_number(
    database_session: DatabaseSession,
    shipment_number: Annotated[
        str,
        Path(min_length=1, max_length=50),
    ],
) -> ShipmentDetailResponse:
    """Return shipment header, lines and status history."""

    return ShipmentService(
        database_session
    ).get_shipment_by_number(shipment_number)


@router.get(
    "/{shipment_id}",
    response_model=ShipmentDetailResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    summary="Get shipment by identifier",
)
def get_shipment(
    database_session: DatabaseSession,
    shipment_id: Annotated[UUID, Path()],
) -> ShipmentDetailResponse:
    """Return shipment header, lines and status history."""

    return ShipmentService(database_session).get_shipment(
        shipment_id
    )