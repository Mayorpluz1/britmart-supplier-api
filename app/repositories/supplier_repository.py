"""Database access operations for BritMart suppliers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.supplier import Supplier
from app.schemas.supplier import SupplierFilterParameters


class SupplierRepository:
    """Read and write access to the supplier operational table."""

    def __init__(self, database_session: Session) -> None:
        self.database_session = database_session

    @staticmethod
    def _apply_filters(
        statement: Select[tuple[Supplier]],
        parameters: SupplierFilterParameters,
    ) -> Select[tuple[Supplier]]:
        """Apply supported supplier and incremental-load filters."""

        if parameters.supplier_status is not None:
            statement = statement.where(
                Supplier.supplier_status
                == parameters.supplier_status.value
            )

        if parameters.risk_rating is not None:
            statement = statement.where(
                Supplier.risk_rating == parameters.risk_rating.value
            )

        if parameters.country_code is not None:
            statement = statement.where(
                Supplier.country_code
                == parameters.country_code.upper()
            )

        if parameters.active_flag is not None:
            statement = statement.where(
                Supplier.active_flag == parameters.active_flag
            )

        if parameters.updated_since is not None:
            statement = statement.where(
                Supplier.updated_at >= parameters.updated_since
            )

        if parameters.updated_before is not None:
            statement = statement.where(
                Supplier.updated_at < parameters.updated_before
            )

        return statement

    def list_suppliers(
        self,
        parameters: SupplierFilterParameters,
    ) -> tuple[list[Supplier], int]:
        """
        Return one supplier page and the total matching record count.

        Ordering by updated_at and supplier_id provides a deterministic
        incremental-extraction sequence for Microsoft Fabric.
        """

        filtered_statement = self._apply_filters(
            select(Supplier),
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
                Supplier.updated_at.asc(),
                Supplier.supplier_id.asc(),
            )
            .offset(offset)
            .limit(parameters.page_size)
        )

        suppliers = list(
            self.database_session.scalars(page_statement).all()
        )

        return suppliers, total_records

    def get_supplier_by_id(
        self,
        supplier_id: UUID,
    ) -> Supplier | None:
        """Return a supplier using its immutable technical identifier."""

        statement = select(Supplier).where(
            Supplier.supplier_id == supplier_id
        )

        return self.database_session.scalar(statement)

    def get_supplier_by_code(
        self,
        supplier_code: str,
    ) -> Supplier | None:
        """Return a supplier using its unique operational business code."""

        statement = select(Supplier).where(
            Supplier.supplier_code == supplier_code.upper()
        )

        return self.database_session.scalar(statement)