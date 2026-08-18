"""Integration tests for the loaded BritMart operational database."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.db.session import (
    check_database_connection,
    check_foreign_key_enforcement,
    engine,
)
from app.models import (
    DistributionCentreReference,
    ProductReference,
    PurchaseOrder,
    PurchaseOrderLine,
    Shipment,
    ShipmentLine,
    ShipmentStatusHistory,
    Supplier,
    SupplierPerformanceEvent,
    SupplierPerformanceMonthly,
    SupplierProduct,
    SupplierStatusHistory,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = PROJECT_ROOT / "data-generators" / "output"

EXPECTED_DATABASE_COUNTS = {
    DistributionCentreReference: 6,
    ProductReference: 2_000,
    Supplier: 50,
    SupplierProduct: 2_600,
    PurchaseOrder: 8_000,
    PurchaseOrderLine: 48_000,
    Shipment: 9_847,
    ShipmentLine: 52_100,
    ShipmentStatusHistory: 36_761,
    SupplierPerformanceEvent: 17_235,
    SupplierPerformanceMonthly: 577,
    SupplierStatusHistory: 0,
}

SOURCE_FILE_MAPPING = {
    DistributionCentreReference: "distribution_centres.csv",
    ProductReference: "products.csv",
    Supplier: "suppliers.csv",
    SupplierProduct: "supplier_products.csv",
    PurchaseOrder: "purchase_orders.csv",
    PurchaseOrderLine: "purchase_order_lines.csv",
    Shipment: "shipments.csv",
    ShipmentLine: "shipment_lines.csv",
    ShipmentStatusHistory: "shipment_status_history.csv",
    SupplierPerformanceEvent: "supplier_performance_events.csv",
    SupplierPerformanceMonthly: "supplier_performance_monthly.csv",
}


@pytest.fixture()
def session() -> Session:
    """Provide a database session and always close it after the test."""

    database_session = Session(engine)

    try:
        yield database_session
    finally:
        database_session.close()


def count_csv_records(path: Path) -> int:
    """Return the number of data rows in a CSV file."""

    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return sum(1 for _ in csv.DictReader(csv_file))


def test_database_connection_is_available() -> None:
    """Confirm that the configured operational database is reachable."""

    assert check_database_connection() is True


def test_sqlite_foreign_key_enforcement_is_enabled() -> None:
    """Confirm that SQLite enforces declared foreign keys."""

    if engine.dialect.name == "sqlite":
        assert check_foreign_key_enforcement() is True


def test_database_contains_expected_tables() -> None:
    """Confirm that all operational tables and Alembic metadata exist."""

    expected_tables = {
        "alembic_version",
        "distribution_centre_reference",
        "product_reference",
        "suppliers",
        "supplier_status_history",
        "supplier_products",
        "purchase_orders",
        "purchase_order_lines",
        "shipments",
        "shipment_lines",
        "shipment_status_history",
        "supplier_performance_events",
        "supplier_performance_monthly",
    }

    actual_tables = set(inspect(engine).get_table_names())

    assert actual_tables == expected_tables


def test_database_is_at_expected_alembic_revision(
    session: Session,
) -> None:
    """Confirm that the database schema is at the approved revision."""

    revision = session.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one()

    assert revision == "54038c26cea6"


@pytest.mark.parametrize(
    ("model", "expected_count"),
    EXPECTED_DATABASE_COUNTS.items(),
)
def test_database_table_counts_match_expected_release(
    session: Session,
    model: type,
    expected_count: int,
) -> None:
    """Confirm that every database table has its approved record count."""

    actual_count = session.scalar(
        select(func.count()).select_from(model)
    )

    assert actual_count == expected_count


@pytest.mark.parametrize(
    ("model", "source_file_name"),
    SOURCE_FILE_MAPPING.items(),
)
def test_database_counts_reconcile_to_source_files(
    session: Session,
    model: type,
    source_file_name: str,
) -> None:
    """Reconcile database row counts to validated release files."""

    source_path = OUTPUT_DIRECTORY / source_file_name

    assert source_path.exists(), f"Missing source file: {source_path}"

    source_count = count_csv_records(source_path)
    database_count = session.scalar(
        select(func.count()).select_from(model)
    )

    assert database_count == source_count


def test_database_contains_no_foreign_key_violations(
    session: Session,
) -> None:
    """Use SQLite's integrity check to detect orphaned records."""

    if engine.dialect.name != "sqlite":
        pytest.skip("PRAGMA foreign_key_check applies only to SQLite.")

    violations = session.execute(
        text("PRAGMA foreign_key_check")
    ).all()

    assert violations == []


def test_purchase_order_headers_reconcile_to_lines(
    session: Session,
) -> None:
    """Recalculate purchase-order totals from their lines."""

    mismatched_orders = session.execute(
        text(
            """
            SELECT
                po.purchase_order_id
            FROM purchase_orders AS po
            JOIN (
                SELECT
                    purchase_order_id,
                    SUM(net_amount) AS line_net_amount,
                    SUM(vat_amount) AS line_vat_amount,
                    SUM(gross_amount) AS line_gross_amount
                FROM purchase_order_lines
                GROUP BY purchase_order_id
            ) AS lines
                ON lines.purchase_order_id = po.purchase_order_id
            WHERE
                ABS(po.total_net_amount - lines.line_net_amount) > 0.05
                OR ABS(
                    po.total_vat_amount - lines.line_vat_amount
                ) > 0.05
                OR ABS(
                    po.total_gross_amount - lines.line_gross_amount
                ) > 0.05
            """
        )
    ).all()

    assert mismatched_orders == []


def test_shipment_headers_reconcile_to_lines(
    session: Session,
) -> None:
    """Recalculate shipment quantities from shipment lines."""

    mismatched_shipments = session.execute(
        text(
            """
            SELECT
                shipment.shipment_id
            FROM shipments AS shipment
            JOIN (
                SELECT
                    shipment_id,
                    SUM(planned_quantity) AS planned_quantity,
                    SUM(shipped_quantity) AS shipped_quantity,
                    SUM(received_quantity) AS received_quantity,
                    SUM(damaged_quantity) AS damaged_quantity,
                    SUM(rejected_quantity) AS rejected_quantity,
                    SUM(accepted_quantity) AS accepted_quantity
                FROM shipment_lines
                GROUP BY shipment_id
            ) AS lines
                ON lines.shipment_id = shipment.shipment_id
            WHERE
                ABS(
                    shipment.total_planned_quantity
                    - lines.planned_quantity
                ) > 0.001
                OR ABS(
                    shipment.total_shipped_quantity
                    - lines.shipped_quantity
                ) > 0.001
                OR ABS(
                    shipment.total_received_quantity
                    - lines.received_quantity
                ) > 0.001
                OR ABS(
                    shipment.total_damaged_quantity
                    - lines.damaged_quantity
                ) > 0.001
                OR ABS(
                    shipment.total_rejected_quantity
                    - lines.rejected_quantity
                ) > 0.001
                OR ABS(
                    shipment.total_accepted_quantity
                    - lines.accepted_quantity
                ) > 0.001
            """
        )
    ).all()

    assert mismatched_shipments == []


def test_incremental_ordering_key_is_complete(
    session: Session,
) -> None:
    """Ensure Fabric can order incremental extraction deterministically."""

    incomplete_records = session.execute(
        text(
            """
            SELECT COUNT(*)
            FROM shipments
            WHERE updated_at IS NULL OR shipment_id IS NULL
            """
        )
    ).scalar_one()

    assert incomplete_records == 0


def test_incremental_shipment_query_has_stable_ordering(
    session: Session,
) -> None:
    """Confirm ordering by watermark and primary key is deterministic."""

    rows = session.execute(
        text(
            """
            SELECT updated_at, shipment_id
            FROM shipments
            ORDER BY updated_at ASC, shipment_id ASC
            LIMIT 500
            """
        )
    ).all()

    assert rows == sorted(rows, key=lambda row: (row[0], row[1]))


def test_loader_rejects_accidental_duplicate_full_load() -> None:
    """Confirm rerunning the loader without --replace is rejected."""

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.load_operational_data",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    combined_output = result.stdout + result.stderr

    assert result.returncode != 0
    assert (
        "not empty" in combined_output.lower()
        or "already contains" in combined_output.lower()
        or "replace" in combined_output.lower()
    )