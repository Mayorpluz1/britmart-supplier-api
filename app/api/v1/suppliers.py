"""Version 1 supplier endpoints for the BritMart API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.database import DatabaseSession
from app.dependencies.security import verify_api_key
from app.schemas.common import ErrorResponse
from app.schemas.supplier import (
    SupplierFilterParameters,
    SupplierListResponse,
    SupplierResponse,
)
from app.services.supplier_service import SupplierService


router = APIRouter(
    prefix="/suppliers",
    tags=["Suppliers"],
    dependencies=[Depends(verify_api_key)],
)


@router.get(
    "",
    response_model=SupplierListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Missing or invalid API key.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "Invalid filter or pagination value.",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": "Operational database unavailable.",
        },
    },
    summary="List suppliers",
    description=(
        "Return a filtered and paginated supplier collection. Results use "
        "stable updated_at and supplier_id ordering for incremental "
        "Microsoft Fabric extraction."
    ),
)
def list_suppliers(
    database_session: DatabaseSession,
    parameters: Annotated[SupplierFilterParameters, Query()],
) -> SupplierListResponse:
    """Return suppliers using controlled filter and pagination values."""

    return SupplierService(database_session).list_suppliers(parameters)


@router.get(
    "/by-code/{supplier_code}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Missing or invalid API key.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Supplier code not found.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "Invalid supplier code.",
        },
    },
    summary="Get supplier by business code",
)
def get_supplier_by_code(
    database_session: DatabaseSession,
    supplier_code: Annotated[
        str,
        Path(
            min_length=1,
            max_length=30,
            examples=["SUP-0001"],
        ),
    ],
) -> SupplierResponse:
    """Return one supplier using its operational code."""

    return SupplierService(database_session).get_supplier_by_code(
        supplier_code
    )


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Missing or invalid API key.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Supplier not found.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ErrorResponse,
            "description": "Invalid supplier identifier.",
        },
    },
    summary="Get supplier by identifier",
)
def get_supplier(
    database_session: DatabaseSession,
    supplier_id: Annotated[
        UUID,
        Path(description="Immutable supplier UUID."),
    ],
) -> SupplierResponse:
    """Return one supplier using its technical identifier."""

    return SupplierService(database_session).get_supplier(supplier_id)