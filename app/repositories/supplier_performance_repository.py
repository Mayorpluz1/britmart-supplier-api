"""Database repository for supplier-performance records."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.supplier_performance import (
    SupplierPerformanceEvent,
    SupplierPerformanceMonthly,
)
from app.schemas.supplier_performance import (
    SupplierPerformanceEventFilterParameters,
    SupplierPerformanceMonthlyFilterParameters,
)


class SupplierPerformanceRepository:
    """Provide read access to supplier-performance data."""

    def __init__(self, database_session: Session) -> None:
        self.database_session = database_session

    @staticmethod
    def _apply_event_filters(
        statement,
        parameters: SupplierPerformanceEventFilterParameters,
    ):
        """Apply event filters to a SQLAlchemy statement."""

        if parameters.supplier_id is not None:
            statement = statement.where(
                SupplierPerformanceEvent.supplier_id
                == parameters.supplier_id
            )

        if parameters.supplier_code is not None:
            statement = statement.where(
                func.upper(
                    SupplierPerformanceEvent.supplier_code
                )
                == parameters.supplier_code.strip().upper()
            )

        if parameters.event_category is not None:
            statement = statement.where(
                SupplierPerformanceEvent.event_category
                == parameters.event_category
            )

        if parameters.severity is not None:
            statement = statement.where(
                SupplierPerformanceEvent.severity
                == parameters.severity
            )

        if parameters.passed_flag is not None:
            statement = statement.where(
                SupplierPerformanceEvent.passed_flag
                == parameters.passed_flag
            )

        if parameters.performance_month is not None:
            statement = statement.where(
                SupplierPerformanceEvent.performance_month
                == parameters.performance_month
            )

        if parameters.shipment_id is not None:
            statement = statement.where(
                SupplierPerformanceEvent.shipment_id
                == parameters.shipment_id
            )

        if parameters.purchase_order_id is not None:
            statement = statement.where(
                SupplierPerformanceEvent.purchase_order_id
                == parameters.purchase_order_id
            )

        if parameters.event_occurred_since is not None:
            statement = statement.where(
                SupplierPerformanceEvent.event_occurred_at
                >= parameters.event_occurred_since
            )

        if parameters.event_occurred_before is not None:
            statement = statement.where(
                SupplierPerformanceEvent.event_occurred_at
                < parameters.event_occurred_before
            )

        if parameters.updated_since is not None:
            statement = statement.where(
                SupplierPerformanceEvent.updated_at
                >= parameters.updated_since
            )

        if parameters.updated_before is not None:
            statement = statement.where(
                SupplierPerformanceEvent.updated_at
                < parameters.updated_before
            )

        return statement

    def list_events(
        self,
        parameters: SupplierPerformanceEventFilterParameters,
    ) -> tuple[list[SupplierPerformanceEvent], int]:
        """Return one filtered event page and its total count."""

        filtered_statement = self._apply_event_filters(
            select(SupplierPerformanceEvent),
            parameters,
        )

        count_statement = self._apply_event_filters(
            select(func.count()).select_from(
                SupplierPerformanceEvent
            ),
            parameters,
        )

        total_records = int(
            self.database_session.scalar(count_statement) or 0
        )

        offset = (
            parameters.page - 1
        ) * parameters.page_size

        records = list(
            self.database_session.scalars(
                filtered_statement.order_by(
                    SupplierPerformanceEvent.updated_at,
                    SupplierPerformanceEvent
                    .supplier_performance_event_id,
                )
                .offset(offset)
                .limit(parameters.page_size)
            ).all()
        )

        return records, total_records

    def get_event_by_id(
        self,
        event_id: UUID,
    ) -> SupplierPerformanceEvent | None:
        """Return one event by UUID."""

        return self.database_session.scalar(
            select(SupplierPerformanceEvent).where(
                SupplierPerformanceEvent
                .supplier_performance_event_id
                == event_id
            )
        )

    @staticmethod
    def _apply_monthly_filters(
        statement,
        parameters: SupplierPerformanceMonthlyFilterParameters,
    ):
        """Apply monthly-scorecard filters."""

        if parameters.supplier_id is not None:
            statement = statement.where(
                SupplierPerformanceMonthly.supplier_id
                == parameters.supplier_id
            )

        if parameters.supplier_code is not None:
            statement = statement.where(
                func.upper(
                    SupplierPerformanceMonthly.supplier_code
                )
                == parameters.supplier_code.strip().upper()
            )

        if parameters.performance_month is not None:
            statement = statement.where(
                SupplierPerformanceMonthly.performance_month
                == parameters.performance_month
            )

        if parameters.performance_rating is not None:
            statement = statement.where(
                SupplierPerformanceMonthly.performance_rating
                == parameters.performance_rating
            )

        if parameters.risk_indicator is not None:
            statement = statement.where(
                SupplierPerformanceMonthly.risk_indicator
                == parameters.risk_indicator
            )

        if parameters.updated_since is not None:
            statement = statement.where(
                SupplierPerformanceMonthly.updated_at
                >= parameters.updated_since
            )

        if parameters.updated_before is not None:
            statement = statement.where(
                SupplierPerformanceMonthly.updated_at
                < parameters.updated_before
            )

        return statement

    def list_monthly_scorecards(
        self,
        parameters: SupplierPerformanceMonthlyFilterParameters,
    ) -> tuple[list[SupplierPerformanceMonthly], int]:
        """Return one monthly-scorecard page and total count."""

        filtered_statement = self._apply_monthly_filters(
            select(SupplierPerformanceMonthly),
            parameters,
        )

        count_statement = self._apply_monthly_filters(
            select(func.count()).select_from(
                SupplierPerformanceMonthly
            ),
            parameters,
        )

        total_records = int(
            self.database_session.scalar(count_statement) or 0
        )

        offset = (
            parameters.page - 1
        ) * parameters.page_size

        records = list(
            self.database_session.scalars(
                filtered_statement.order_by(
                    SupplierPerformanceMonthly.updated_at,
                    SupplierPerformanceMonthly
                    .supplier_performance_monthly_id,
                )
                .offset(offset)
                .limit(parameters.page_size)
            ).all()
        )

        return records, total_records

    def get_monthly_scorecard_by_id(
        self,
        scorecard_id: UUID,
    ) -> SupplierPerformanceMonthly | None:
        """Return one monthly scorecard by UUID."""

        return self.database_session.scalar(
            select(SupplierPerformanceMonthly).where(
                SupplierPerformanceMonthly
                .supplier_performance_monthly_id
                == scorecard_id
            )
        )

    def get_supplier_monthly_scorecard(
        self,
        supplier_id: UUID,
        performance_month: str,
    ) -> SupplierPerformanceMonthly | None:
        """Return a supplier scorecard for a particular month."""

        return self.database_session.scalar(
            select(SupplierPerformanceMonthly).where(
                SupplierPerformanceMonthly.supplier_id
                == supplier_id,
                SupplierPerformanceMonthly.performance_month
                == performance_month,
            )
        )