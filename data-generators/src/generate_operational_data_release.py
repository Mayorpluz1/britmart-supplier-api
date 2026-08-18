"""Generate the BritMart integrated operational-data release manifest."""

from __future__ import annotations

import csv
import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_GENERATORS_DIRECTORY = PROJECT_ROOT / "data-generators"
CONFIG_PATH = (
    DATA_GENERATORS_DIRECTORY
    / "config"
    / "operational_release_config.json"
)
DEFAULT_OUTPUT_DIRECTORY = DATA_GENERATORS_DIRECTORY / "output"
MANIFEST_FILE_NAME = "operational_data_release_manifest.json"

RELEASE_NAMESPACE = uuid.UUID("fd9158d2-5727-4ab7-9adb-911ddd86207d")


def load_json(path: Path) -> dict[str, Any]:
    """Load and return a JSON object."""

    if not path.exists():
        raise FileNotFoundError(f"Required JSON file does not exist: {path}")

    with path.open("r", encoding="utf-8") as file:
        value = json.load(file)

    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")

    return value


def resolve_output_directory(config: dict[str, Any]) -> Path:
    """Resolve the directory containing generated operational datasets."""

    configured_path = config.get("generated_data_directory")

    if not configured_path:
        return DEFAULT_OUTPUT_DIRECTORY

    path = Path(str(configured_path))

    if path.is_absolute():
        return path.resolve()

    return (CONFIG_PATH.parent / path).resolve()


def validate_release_timestamp(timestamp_text: str) -> str:
    """Validate that the configured release timestamp is UTC."""

    if not timestamp_text:
        raise ValueError("release_timestamp_utc must be populated.")

    normalised = timestamp_text.replace("Z", "+00:00")

    try:
        parsed_timestamp = datetime.fromisoformat(normalised)
    except ValueError as error:
        raise ValueError(
            "release_timestamp_utc must be a valid ISO-8601 timestamp."
        ) from error

    if parsed_timestamp.tzinfo is None:
        raise ValueError("release_timestamp_utc must include a UTC offset.")

    if parsed_timestamp.utcoffset() is None:
        raise ValueError("release_timestamp_utc must include a UTC offset.")

    if parsed_timestamp.utcoffset().total_seconds() != 0:
        raise ValueError("release_timestamp_utc must use UTC.")

    return parsed_timestamp.isoformat().replace("+00:00", "Z")


def calculate_file_hash(path: Path, algorithm: str) -> str:
    """Calculate the configured cryptographic hash for a file."""

    try:
        digest = hashlib.new(algorithm)
    except ValueError as error:
        raise ValueError(
            f"Unsupported hash algorithm: {algorithm}"
        ) from error

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def inspect_csv(
    path: Path,
    primary_key: list[str],
    encoding: str,
) -> dict[str, Any]:
    """Inspect a CSV file and validate its primary key."""

    with path.open("r", encoding=encoding, newline="") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError(f"Dataset has no header row: {path}")

        columns = list(reader.fieldnames)

        missing_key_columns = [
            column for column in primary_key if column not in columns
        ]

        if missing_key_columns:
            raise ValueError(
                f"{path.name} is missing primary-key columns: "
                f"{missing_key_columns}"
            )

        record_count = 0
        seen_keys: set[tuple[str, ...]] = set()

        for row_number, row in enumerate(reader, start=2):
            record_count += 1

            key_value = tuple(
                (row.get(column) or "").strip()
                for column in primary_key
            )

            if any(not value for value in key_value):
                raise ValueError(
                    f"Blank primary-key value in {path.name} "
                    f"at CSV row {row_number}."
                )

            if key_value in seen_keys:
                raise ValueError(
                    f"Duplicate primary key {key_value} "
                    f"in {path.name}."
                )

            seen_keys.add(key_value)

    return {
        "record_count": record_count,
        "column_count": len(columns),
        "columns": columns,
        "primary_key_unique": True,
        "primary_key_null_count": 0,
    }


def validate_dataset_configuration(
    dataset: dict[str, Any],
    position: int,
) -> None:
    """Validate one configured dataset definition."""

    required_fields = {
        "dataset_name",
        "file_name",
        "domain",
        "source_owner",
        "primary_key",
        "expected_record_count",
    }

    missing_fields = sorted(required_fields - dataset.keys())

    if missing_fields:
        raise ValueError(
            f"Dataset configuration at position {position} "
            f"is missing fields: {missing_fields}"
        )

    primary_key = dataset["primary_key"]

    if not isinstance(primary_key, list) or not primary_key:
        raise ValueError(
            f"{dataset['dataset_name']} must define a non-empty "
            "primary_key list."
        )

    expected_record_count = dataset["expected_record_count"]

    if (
        isinstance(expected_record_count, bool)
        or not isinstance(expected_record_count, int)
        or expected_record_count < 0
    ):
        raise ValueError(
            f"{dataset['dataset_name']} has an invalid "
            "expected_record_count."
        )


def validate_release_configuration(config: dict[str, Any]) -> None:
    """Validate the operational release configuration."""

    required_top_level_fields = {
        "release_name",
        "release_version",
        "release_type",
        "source_system",
        "release_timestamp_utc",
        "hash_algorithm",
        "encoding",
        "required_datasets",
        "expected_dataset_count",
        "expected_total_record_count",
        "required_reconciliation_controls",
    }

    missing_fields = sorted(required_top_level_fields - config.keys())

    if missing_fields:
        raise ValueError(
            f"Operational release configuration is missing: "
            f"{missing_fields}"
        )

    required_datasets = config["required_datasets"]

    if not isinstance(required_datasets, list) or not required_datasets:
        raise ValueError("required_datasets must be a non-empty list.")

    for position, dataset in enumerate(required_datasets, start=1):
        if not isinstance(dataset, dict):
            raise ValueError(
                f"Dataset configuration at position {position} "
                "must be a JSON object."
            )

        validate_dataset_configuration(dataset, position)

    dataset_names = [
        dataset["dataset_name"] for dataset in required_datasets
    ]
    file_names = [
        dataset["file_name"] for dataset in required_datasets
    ]

    if len(dataset_names) != len(set(dataset_names)):
        raise ValueError("Configured dataset names must be unique.")

    if len(file_names) != len(set(file_names)):
        raise ValueError("Configured dataset file names must be unique.")

    if config["expected_dataset_count"] != len(required_datasets):
        raise ValueError(
            "expected_dataset_count does not match required_datasets."
        )

    configured_total = sum(
        dataset["expected_record_count"]
        for dataset in required_datasets
    )

    if config["expected_total_record_count"] != configured_total:
        raise ValueError(
            "expected_total_record_count does not match the sum of "
            "configured dataset counts."
        )

    controls = config["required_reconciliation_controls"]

    if not isinstance(controls, list) or not controls:
        raise ValueError(
            "required_reconciliation_controls must be a non-empty list."
        )

    if len(controls) != len(set(controls)):
        raise ValueError(
            "required_reconciliation_controls must be unique."
        )

    validate_release_timestamp(config["release_timestamp_utc"])


def build_dataset_manifest_entry(
    dataset: dict[str, Any],
    output_directory: Path,
    hash_algorithm: str,
    encoding: str,
) -> dict[str, Any]:
    """Build the manifest entry for one operational dataset."""

    dataset_path = output_directory / dataset["file_name"]

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Required operational dataset does not exist: {dataset_path}"
        )

    if not dataset_path.is_file():
        raise ValueError(
            f"Operational dataset path is not a file: {dataset_path}"
        )

    inspection = inspect_csv(
        path=dataset_path,
        primary_key=dataset["primary_key"],
        encoding=encoding,
    )

    expected_record_count = dataset["expected_record_count"]
    actual_record_count = inspection["record_count"]

    if actual_record_count != expected_record_count:
        raise ValueError(
            f"{dataset['dataset_name']} contains "
            f"{actual_record_count} records; expected "
            f"{expected_record_count}."
        )

    return {
        "dataset_name": dataset["dataset_name"],
        "file_name": dataset["file_name"],
        "domain": dataset["domain"],
        "source_owner": dataset["source_owner"],
        "primary_key": dataset["primary_key"],
        "expected_record_count": expected_record_count,
        "actual_record_count": actual_record_count,
        "record_count_reconciled": True,
        "column_count": inspection["column_count"],
        "columns": inspection["columns"],
        "primary_key_unique": inspection["primary_key_unique"],
        "primary_key_null_count": inspection["primary_key_null_count"],
        "file_size_bytes": dataset_path.stat().st_size,
        "hash_algorithm": hash_algorithm,
        "file_hash": calculate_file_hash(
            dataset_path,
            hash_algorithm,
        ),
    }


def create_release_identity(
    config: dict[str, Any],
    dataset_entries: list[dict[str, Any]],
) -> tuple[str, str]:
    """Create deterministic release fingerprint and release identifier."""

    identity_payload = {
        "release_name": config["release_name"],
        "release_version": config["release_version"],
        "release_type": config["release_type"],
        "release_timestamp_utc": config["release_timestamp_utc"],
        "datasets": [
            {
                "dataset_name": entry["dataset_name"],
                "record_count": entry["actual_record_count"],
                "file_hash": entry["file_hash"],
            }
            for entry in dataset_entries
        ],
    }

    canonical_payload = json.dumps(
        identity_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    release_fingerprint = hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()

    release_id = str(
        uuid.uuid5(RELEASE_NAMESPACE, release_fingerprint)
    )

    return release_id, release_fingerprint


def build_release_manifest(
    config: dict[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    """Build the complete integrated operational release manifest."""

    hash_algorithm = str(config["hash_algorithm"]).lower()
    encoding = str(config["encoding"])

    dataset_entries = [
        build_dataset_manifest_entry(
            dataset=dataset,
            output_directory=output_directory,
            hash_algorithm=hash_algorithm,
            encoding=encoding,
        )
        for dataset in config["required_datasets"]
    ]

    actual_dataset_count = len(dataset_entries)
    actual_total_record_count = sum(
        entry["actual_record_count"]
        for entry in dataset_entries
    )

    expected_dataset_count = config["expected_dataset_count"]
    expected_total_record_count = config["expected_total_record_count"]

    if actual_dataset_count != expected_dataset_count:
        raise ValueError(
            f"Release contains {actual_dataset_count} datasets; "
            f"expected {expected_dataset_count}."
        )

    if actual_total_record_count != expected_total_record_count:
        raise ValueError(
            f"Release contains {actual_total_record_count} records; "
            f"expected {expected_total_record_count}."
        )

    release_id, release_fingerprint = create_release_identity(
        config,
        dataset_entries,
    )

    return {
        "release_id": release_id,
        "release_name": config["release_name"],
        "release_version": config["release_version"],
        "release_type": config["release_type"],
        "source_system": config["source_system"],
        "release_timestamp_utc": validate_release_timestamp(
            config["release_timestamp_utc"]
        ),
        "release_fingerprint": release_fingerprint,
        "hash_algorithm": hash_algorithm,
        "encoding": encoding,
        "expected_dataset_count": expected_dataset_count,
        "actual_dataset_count": actual_dataset_count,
        "expected_total_record_count": expected_total_record_count,
        "actual_total_record_count": actual_total_record_count,
        "dataset_count_reconciled": True,
        "record_count_reconciled": True,
        "required_reconciliation_controls": (
            config["required_reconciliation_controls"]
        ),
        "reconciliation_control_count": len(
            config["required_reconciliation_controls"]
        ),
        "approved_for_database_loading": bool(
            config.get("approved_for_database_loading", False)
        ),
        "approved_for_fabric_ingestion": bool(
            config.get("approved_for_fabric_ingestion", False)
        ),
        "datasets": dataset_entries,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    """Write deterministic, formatted JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(
            value,
            file,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        file.write("\n")


def main() -> None:
    """Generate the integrated operational-data release manifest."""

    config = load_json(CONFIG_PATH)
    validate_release_configuration(config)

    output_directory = resolve_output_directory(config)

    if not output_directory.exists():
        raise FileNotFoundError(
            f"Generated-data directory does not exist: "
            f"{output_directory}"
        )

    manifest = build_release_manifest(
        config=config,
        output_directory=output_directory,
    )

    manifest_path = output_directory / MANIFEST_FILE_NAME
    write_json(manifest_path, manifest)

    print(
        "BritMart integrated operational-data release manifest "
        "generated successfully."
    )
    print(f"Release ID: {manifest['release_id']}")
    print(f"Datasets: {manifest['actual_dataset_count']}")
    print(f"Total records: {manifest['actual_total_record_count']}")
    print(
        "Reconciliation controls: "
        f"{manifest['reconciliation_control_count']}"
    )
    print(
        "Approved for database loading: "
        f"{manifest['approved_for_database_loading']}"
    )
    print(
        "Approved for Fabric ingestion: "
        f"{manifest['approved_for_fabric_ingestion']}"
    )
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()