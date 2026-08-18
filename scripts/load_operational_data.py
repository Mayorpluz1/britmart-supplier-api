"""Load the approved BritMart operational release into the API database."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import uuid
from collections.abc import Callable, Iterator
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Integer,
    JSON,
    Numeric,
    String,
    Uuid,
    delete,
    func,
    insert,
    select,
)
from sqlalchemy.orm import Session

from app.db.session import (
    check_foreign_key_enforcement,
    session_scope,
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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIRECTORY = (
    PROJECT_ROOT / "data-generators" / "output"
)
MANIFEST_PATH = (
    OUTPUT_DIRECTORY
    / "operational_data_release_manifest.json"
)
VALIDATION_REPORT_PATH = (
    OUTPUT_DIRECTORY
    / "operational_data_validation_report.json"
)

BATCH_SIZE = 2000

ModelType = type[Any]
RowTransform = Callable[
    [dict[str, str], datetime],
    dict[str, Any],
]


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""

    if not path.exists():
        raise FileNotFoundError(
            f"Required release-control file does not exist: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        value = json.load(file)

    if not isinstance(value, dict):
        raise ValueError(
            f"Expected a JSON object in {path}"
        )

    return value


def parse_datetime(value: str) -> datetime:
    """Parse an ISO-8601 timestamp."""

    normalised = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(normalised)


def parse_date(value: str) -> date:
    """Parse an ISO-formatted date."""

    return date.fromisoformat(value.strip())


def parse_boolean(value: str) -> bool:
    """Parse a controlled Boolean text value."""

    normalised = value.strip().lower()

    if normalised in {"true", "1", "yes", "y"}:
        return True

    if normalised in {"false", "0", "no", "n"}:
        return False

    raise ValueError(
        f"Invalid Boolean value: {value!r}"
    )


def parse_string_list(value: str) -> list[str]:
    """Parse a source list represented as JSON or delimited text."""

    stripped_value = value.strip()

    if not stripped_value:
        return []

    if stripped_value.startswith("["):
        parsed_value = json.loads(stripped_value)

        if not isinstance(parsed_value, list):
            raise ValueError(
                "Expected category_codes JSON to be a list."
            )

        return [
            str(item).strip()
            for item in parsed_value
            if str(item).strip()
        ]

    delimiter = None

    for candidate in ("|", ";", ","):
        if candidate in stripped_value:
            delimiter = candidate
            break

    if delimiter is None:
        return [stripped_value]

    return [
        item.strip()
        for item in stripped_value.split(delimiter)
        if item.strip()
    ]


def convert_value(
    raw_value: str,
    column: Any,
) -> Any:
    """Convert one CSV value using SQLAlchemy column metadata."""

    if raw_value == "":
        if column.nullable:
            return None

        if isinstance(column.type, String):
            return ""

        raise ValueError(
            f"Column {column.name} cannot be blank."
        )

    column_type = column.type

    if isinstance(column_type, Uuid):
        return uuid.UUID(raw_value)

    if isinstance(column_type, Boolean):
        return parse_boolean(raw_value)

    if isinstance(column_type, Integer):
        return int(raw_value)

    if isinstance(column_type, Numeric):
        return Decimal(raw_value)

    if isinstance(column_type, DateTime):
        return parse_datetime(raw_value)

    if isinstance(column_type, Date):
        return parse_date(raw_value)

    if isinstance(column_type, JSON):
        return parse_string_list(raw_value)

    return raw_value


def default_transform(
    raw_row: dict[str, str],
    release_timestamp: datetime,
) -> dict[str, Any]:
    """Return an unchanged row mapping."""

    del release_timestamp
    return dict(raw_row)


def transform_product_reference(
    raw_row: dict[str, str],
    release_timestamp: datetime,
) -> dict[str, Any]:
    """Add reference synchronisation metadata to a product."""

    transformed = dict(raw_row)
    transformed["source_updated_at"] = raw_row[
        "updated_at"
    ]
    transformed["synchronised_at"] = (
        release_timestamp.isoformat()
    )
    transformed["version_number"] = "1"

    return transformed


def transform_distribution_centre_reference(
    raw_row: dict[str, str],
    release_timestamp: datetime,
) -> dict[str, Any]:
    """Add synchronisation metadata to a distribution centre."""

    transformed = dict(raw_row)
    transformed["source_updated_at"] = raw_row[
        "updated_at"
    ]
    transformed["synchronised_at"] = (
        release_timestamp.isoformat()
    )
    transformed["version_number"] = "1"

    return transformed


DATASET_LOAD_PLAN: list[
    tuple[str, ModelType, RowTransform]
] = [
    (
        "distribution_centres",
        DistributionCentreReference,
        transform_distribution_centre_reference,
    ),
    (
        "products",
        ProductReference,
        transform_product_reference,
    ),
    (
        "suppliers",
        Supplier,
        default_transform,
    ),
    (
        "supplier_products",
        SupplierProduct,
        default_transform,
    ),
    (
        "purchase_orders",
        PurchaseOrder,
        default_transform,
    ),
    (
        "purchase_order_lines",
        PurchaseOrderLine,
        default_transform,
    ),
    (
        "shipments",
        Shipment,
        default_transform,
    ),
    (
        "shipment_lines",
        ShipmentLine,
        default_transform,
    ),
    (
        "shipment_status_history",
        ShipmentStatusHistory,
        default_transform,
    ),
    (
        "supplier_performance_events",
        SupplierPerformanceEvent,
        default_transform,
    ),
    (
        "supplier_monthly_scorecards",
        SupplierPerformanceMonthly,
        default_transform,
    ),
]

DELETE_ORDER: list[ModelType] = [
    SupplierPerformanceMonthly,
    SupplierPerformanceEvent,
    ShipmentStatusHistory,
    ShipmentLine,
    Shipment,
    PurchaseOrderLine,
    PurchaseOrder,
    SupplierProduct,
    SupplierStatusHistory,
    Supplier,
    ProductReference,
    DistributionCentreReference,
]


def calculate_file_hash(
    path: Path,
    algorithm: str,
) -> str:
    """Calculate a release dataset hash."""

    digest = hashlib.new(algorithm)

    with path.open("rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def validate_release_controls(
    manifest: dict[str, Any],
    validation_report: dict[str, Any],
) -> None:
    """Validate approval and release identity before loading."""

    if (
        validation_report.get("overall_status")
        != "PASSED"
    ):
        raise ValueError(
            "Operational validation report is not PASSED."
        )

    if not manifest.get(
        "approved_for_database_loading"
    ):
        raise ValueError(
            "Release is not approved for database loading."
        )

    if not validation_report.get(
        "approved_for_database_loading"
    ):
        raise ValueError(
            "Validated release is not approved for "
            "database loading."
        )

    if (
        validation_report.get("release_id")
        != manifest.get("release_id")
    ):
        raise ValueError(
            "Validation report release_id does not match "
            "the manifest."
        )

    if (
        validation_report.get("release_fingerprint")
        != manifest.get("release_fingerprint")
    ):
        raise ValueError(
            "Validation report fingerprint does not match "
            "the manifest."
        )

    if (
        manifest.get("actual_dataset_count") != 18
        or manifest.get("actual_total_record_count")
        != 278424
    ):
        raise ValueError(
            "Operational release totals are not approved."
        )

    if (
        validation_report.get(
            "passed_component_validation_count"
        )
        != validation_report.get(
            "component_validation_count"
        )
    ):
        raise ValueError(
            "Not all component validations passed."
        )

    if (
        validation_report.get(
            "passed_reconciliation_control_count"
        )
        != validation_report.get(
            "reconciliation_control_count"
        )
    ):
        raise ValueError(
            "Not all reconciliation controls passed."
        )


def build_manifest_index(
    manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Index manifested datasets by logical name."""

    datasets = manifest.get("datasets")

    if not isinstance(datasets, list):
        raise ValueError(
            "Manifest datasets must be a list."
        )

    manifest_index = {
        dataset["dataset_name"]: dataset
        for dataset in datasets
    }

    required_names = {
        dataset_name
        for dataset_name, _, _ in DATASET_LOAD_PLAN
    }

    missing_names = sorted(
        required_names - set(manifest_index)
    )

    if missing_names:
        raise ValueError(
            "Manifest is missing loadable datasets: "
            f"{missing_names}"
        )

    return manifest_index


def validate_manifested_file(
    manifest_entry: dict[str, Any],
) -> Path:
    """Validate the current file against its manifested hash."""

    dataset_path = (
        OUTPUT_DIRECTORY / manifest_entry["file_name"]
    )

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Manifested dataset does not exist: {dataset_path}"
        )

    hash_algorithm = manifest_entry["hash_algorithm"]
    actual_hash = calculate_file_hash(
        dataset_path,
        hash_algorithm,
    )

    if actual_hash != manifest_entry["file_hash"]:
        raise ValueError(
            f"Hash mismatch for {dataset_path.name}."
        )

    return dataset_path


def prepare_row(
    raw_row: dict[str, str],
    model: ModelType,
    transform: RowTransform,
    release_timestamp: datetime,
) -> dict[str, Any]:
    """Transform and type one CSV row for database insertion."""

    transformed_row = transform(
        raw_row,
        release_timestamp,
    )

    prepared_row: dict[str, Any] = {}

    for column in model.__table__.columns:
        if column.name not in transformed_row:
            continue

        raw_value = transformed_row[column.name]

        if not isinstance(raw_value, str):
            raw_value = str(raw_value)

        prepared_row[column.name] = convert_value(
            raw_value,
            column,
        )

    return prepared_row


def iter_prepared_rows(
    dataset_path: Path,
    model: ModelType,
    transform: RowTransform,
    release_timestamp: datetime,
) -> Iterator[dict[str, Any]]:
    """Yield typed database rows from a CSV dataset."""

    with dataset_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError(
                f"{dataset_path.name} has no CSV header."
            )

        for row_number, raw_row in enumerate(
            reader,
            start=2,
        ):
            try:
                yield prepare_row(
                    raw_row=raw_row,
                    model=model,
                    transform=transform,
                    release_timestamp=release_timestamp,
                )
            except Exception as error:
                raise ValueError(
                    f"Failed to prepare {dataset_path.name} "
                    f"at CSV row {row_number}: {error}"
                ) from error


def insert_in_batches(
    session: Session,
    model: ModelType,
    rows: Iterator[dict[str, Any]],
) -> int:
    """Insert prepared rows in controlled batches."""

    batch: list[dict[str, Any]] = []
    inserted_count = 0

    for row in rows:
        batch.append(row)

        if len(batch) >= BATCH_SIZE:
            session.execute(insert(model), batch)
            inserted_count += len(batch)
            batch.clear()

    if batch:
        session.execute(insert(model), batch)
        inserted_count += len(batch)

    return inserted_count


def count_table_rows(
    session: Session,
    model: ModelType,
) -> int:
    """Return the current record count for a model."""

    statement = select(func.count()).select_from(model)
    return int(session.scalar(statement) or 0)


def ensure_target_tables_are_empty(
    session: Session,
) -> None:
    """Prevent accidental duplicate operational loads."""

    populated_tables = {
        model.__tablename__: count_table_rows(
            session,
            model,
        )
        for _, model, _ in DATASET_LOAD_PLAN
        if count_table_rows(session, model) > 0
    }

    if populated_tables:
        raise RuntimeError(
            "Target operational tables are not empty. "
            "Use --replace only when an intentional full "
            f"reload is required. Populated tables: "
            f"{populated_tables}"
        )


def clear_target_tables(session: Session) -> None:
    """Delete operational records in reverse dependency order."""

    for model in DELETE_ORDER:
        session.execute(delete(model))


def load_operational_release(
    replace_existing: bool,
) -> dict[str, int]:
    """Load the complete validated release transactionally."""

    if not check_foreign_key_enforcement():
        raise RuntimeError(
            "Database foreign-key enforcement is disabled."
        )

    manifest = load_json(MANIFEST_PATH)
    validation_report = load_json(
        VALIDATION_REPORT_PATH
    )

    validate_release_controls(
        manifest,
        validation_report,
    )

    manifest_index = build_manifest_index(manifest)

    release_timestamp = parse_datetime(
        manifest["release_timestamp_utc"]
    )

    load_counts: dict[str, int] = {}

    with session_scope() as session:
        if replace_existing:
            clear_target_tables(session)
        else:
            ensure_target_tables_are_empty(session)

        for dataset_name, model, transform in (
            DATASET_LOAD_PLAN
        ):
            manifest_entry = manifest_index[dataset_name]
            dataset_path = validate_manifested_file(
                manifest_entry
            )

            prepared_rows = iter_prepared_rows(
                dataset_path=dataset_path,
                model=model,
                transform=transform,
                release_timestamp=release_timestamp,
            )

            inserted_count = insert_in_batches(
                session=session,
                model=model,
                rows=prepared_rows,
            )

            expected_count = int(
                manifest_entry["actual_record_count"]
            )

            if inserted_count != expected_count:
                raise ValueError(
                    f"{dataset_name} inserted "
                    f"{inserted_count} rows; expected "
                    f"{expected_count}."
                )

            database_count = count_table_rows(
                session,
                model,
            )

            if database_count != expected_count:
                raise ValueError(
                    f"{model.__tablename__} contains "
                    f"{database_count} rows after loading; "
                    f"expected {expected_count}."
                )

            load_counts[model.__tablename__] = (
                database_count
            )

        supplier_history_count = count_table_rows(
            session,
            SupplierStatusHistory,
        )

        if supplier_history_count != 0:
            raise ValueError(
                "supplier_status_history must be empty "
                "during the baseline load."
            )

        load_counts[
            SupplierStatusHistory.__tablename__
        ] = supplier_history_count

    return load_counts


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Load the approved BritMart operational release "
            "into the configured API database."
        )
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "Intentionally replace existing operational data "
            "inside one transaction."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """Run the controlled operational-data load."""

    arguments = parse_arguments()

    load_counts = load_operational_release(
        replace_existing=arguments.replace,
    )

    total_loaded = sum(load_counts.values())

    print(
        "BritMart operational database load completed "
        "successfully."
    )

    for table_name, record_count in load_counts.items():
        print(f"{table_name}: {record_count}")

    print(f"Total database records: {total_loaded}")
    print("Transaction status: COMMITTED")
    print("Foreign-key enforcement: ENABLED")


if __name__ == "__main__":
    main()