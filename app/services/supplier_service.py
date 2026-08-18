"""Business services for BritMart supplier operations."""

from __future__ import annotations

from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.supplier_repository import SupplierRepository
from app.schemas.common import PaginationMetadata
from app.schemas.supplier import (
    SupplierFilterParameters,
    SupplierListResponse,
    SupplierResponse,
    SupplierSummaryResponse,
)


class SupplierService:
    """Coordinate supplier business rules and response construction."""

    def __init__(self, database_session: Session) -> None:
        self.repository = SupplierRepository(database_session)

    def list_suppliers(
        self,
        parameters: SupplierFilterParameters,
    ) -> SupplierListResponse:
        """Return suppliers with filtering and pagination metadata."""

        suppliers, total_records = self.repository.list_suppliers(
            parameters
        )

        total_pages = (
            ceil(total_records / parameters.page_size)
            if total_records > 0
            else 0
        )

        items = [
            SupplierSummaryResponse.model_validate(supplier)
            for supplier in suppliers
        ]

        pagination = PaginationMetadata(
            page=parameters.page,
            page_size=parameters.page_size,
            total_records=total_records,
            total_pages=total_pages,
            has_next=parameters.page < total_pages,
            has_previous=parameters.page > 1 and total_pages > 0,
        )

        return SupplierListResponse(
            items=items,
            pagination=pagination,
        )

    def get_supplier(
        self,
        supplier_id: UUID,
    ) -> SupplierResponse:
        """Return one supplier or raise a controlled 404 response."""

        supplier = self.repository.get_supplier_by_id(supplier_id)

        if supplier is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "SUPPLIER_NOT_FOUND",
                    "message": (
                        f"Supplier '{supplier_id}' does not exist."
                    ),
                    "field": "supplier_id",
                },
            )

        return SupplierResponse.model_validate(supplier)

    def get_supplier_by_code(
        self,
        supplier_code: str,
    ) -> SupplierResponse:
        """Return one supplier using its operational business code."""

        normalised_supplier_code = supplier_code.strip().upper()
        supplier = self.repository.get_supplier_by_code(
            normalised_supplier_code
        )

        if supplier is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "SUPPLIER_NOT_FOUND",
                    "message": (
                        f"Supplier code '{normalised_supplier_code}' "
                        "does not exist."
                    ),
                    "field": "supplier_code",
                },
            )

        return SupplierResponse.model_validate(supplier)